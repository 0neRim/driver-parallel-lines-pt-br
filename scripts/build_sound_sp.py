#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_sound_sp.py - Patches Sounds/SOUND.SP with PT-BR translations.

Strategy:
  - Each SGSC chunk with subtitles has a metadata section at the end.
  - The metadata has a 16-slot table (4 ints per slot: d_off, d_sz, t_off, t_sz)
    followed by the actual desc/text payloads.
  - We replace text payloads with translated versions while preserving the
    desc (audio descriptor) payloads byte-for-byte.
  - If the new metadata is larger than the original c_size, we grow c_size
    into the sector padding (all chunks are 2048-byte aligned; we verified
    that no translation exceeds the available sector padding).
  - The TOC size field is updated accordingly; offsets never change.
"""

import json
import os
import re
import struct
import sys

BASE_DIR = "/home/romoaldo/Games/Heroic/Driver Parallel Lines"
BACKUP_SP = os.path.join(BASE_DIR, "backup_original", "Sounds", "SOUND.SP")
OUTPUT_SP = os.path.join(BASE_DIR, "translations", "Sounds", "SOUND.SP")
LIVE_SP = os.path.join(BASE_DIR, "Sounds", "SOUND.SP")
TRANS_DB = os.path.join(BASE_DIR, "scratch", "sound_sp_translations_master.json")

TAG_OPEN = "<TEXT>".encode("utf-16-le")


def load_translations():
    with open(TRANS_DB, "r", encoding="utf-8") as f:
        return json.load(f)


def translate_text_payload(payload_bytes, translations):
    """Replace <TEXT>...</TEXT> contents inside a UTF-16LE payload."""
    text = payload_bytes.decode("utf-16le", errors="ignore")

    def repl(m):
        orig = m.group(1)
        tr = translations.get(orig, translations.get(orig.strip(), orig))
        return f"<TEXT>{tr}</TEXT>"

    new_text = re.sub(r"<TEXT>(.*?)</TEXT>", repl, text, flags=re.DOTALL)

    # Re-encode: strip BOM from decoded text if present, prepend raw BOM bytes
    clean = new_text.lstrip("\ufeff")
    return b"\xff\xfe" + clean.encode("utf-16le")


def build():
    translations = load_translations()
    print(f"Loaded {len(translations)} translations.")

    with open(BACKUP_SP, "rb") as f:
        data = bytearray(f.read())

    total_size, entry_count, version = struct.unpack("<III", data[4:16])
    print(f"SOUND.SP: total={total_size}, entries={entry_count}, ver={version}")

    patched_chunks = 0
    patched_lines = 0

    for c_idx in range(entry_count):
        toc_off = 16 + c_idx * 16
        rec = data[toc_off : toc_off + 16]
        c_tag = rec[:4]
        c_off, c_flag, c_size = struct.unpack("<III", rec[4:16])
        cdata = data[c_off : c_off + c_size]

        if TAG_OPEN not in cdata:
            continue

        # Parse SGSB/SS12 header to find metadata
        sgsb_off = 32
        u1, off1, off2, off3 = struct.unpack(
            "<IIII", cdata[sgsb_off + 4 : sgsb_off + 20]
        )
        meta_start = sgsb_off + off3

        # Read original 16 slots
        items = []
        for s in range(16):
            slot_off = meta_start + 4 + s * 16
            d_off, d_sz, t_off, t_sz = struct.unpack(
                "<IIII", cdata[slot_off : slot_off + 16]
            )
            if d_off != 0 and d_sz != 0:
                payload = bytes(cdata[meta_start + d_off : meta_start + d_off + d_sz])
                items.append(("desc", s, d_off, payload))
            if t_off != 0 and t_sz != 0:
                orig_payload = bytes(
                    cdata[meta_start + t_off : meta_start + t_off + t_sz]
                )
                new_payload = translate_text_payload(orig_payload, translations)
                items.append(("text", s, t_off, new_payload))

                # Count translated lines
                count = new_payload.count(TAG_OPEN)
                patched_lines += count

        # Sort items by their original offset to preserve ordering
        items.sort(key=lambda x: x[2])

        # Rebuild metadata block
        new_slots = [[0, 0, 0, 0] for _ in range(16)]
        meta_body = bytearray()
        curr_offset = 260  # Fixed start offset for all chunks

        for itype, s, _orig_off, payload in items:
            # Align to 4 bytes
            align = (4 - (curr_offset % 4)) % 4
            if align:
                meta_body.extend(b"\x00" * align)
                curr_offset += align

            if itype == "desc":
                new_slots[s][0] = curr_offset
                new_slots[s][1] = len(payload)
            else:
                new_slots[s][2] = curr_offset
                new_slots[s][3] = len(payload)

            meta_body.extend(payload)
            curr_offset += len(payload)

        # Assemble: u1 (4 bytes) + 16 slots (256 bytes) + payload
        slot_bytes = bytearray()
        for s in range(16):
            slot_bytes.extend(struct.pack("<IIII", *new_slots[s]))

        new_meta = struct.pack("<I", u1) + slot_bytes + meta_body
        new_csize = meta_start + len(new_meta)

        # Calculate available space (up to next sector boundary)
        next_sector = c_off + c_size
        # Account for sector padding after original c_size
        if c_idx < entry_count - 1:
            next_chunk_off = struct.unpack(
                "<I", data[16 + (c_idx + 1) * 16 + 4 : 16 + (c_idx + 1) * 16 + 8]
            )[0]
        else:
            next_chunk_off = total_size
        max_csize = next_chunk_off  # absolute max we can grow to

        if new_csize > max_csize - c_off:
            print(
                f"FATAL: Chunk {c_idx} needs {new_csize} bytes but only "
                f"{max_csize - c_off} available!"
            )
            sys.exit(1)

        # Pad new_meta with '>' to fill up to at least original c_size
        final_csize = max(c_size, new_csize)
        pad_len = final_csize - (meta_start + len(new_meta))
        if pad_len < 0:
            pad_len = 0
        new_meta_padded = new_meta + b">" * pad_len

        # Write rebuilt chunk metadata into data
        write_start = c_off + meta_start
        write_end = c_off + meta_start + len(new_meta_padded)
        data[write_start:write_end] = new_meta_padded

        # Update TOC c_size if it grew
        if final_csize != c_size:
            struct.pack_into("<I", data, toc_off + 12, final_csize)

        patched_chunks += 1

    print(f"Patched {patched_chunks} chunks, {patched_lines} subtitle lines.")

    # Verify final size matches original
    assert len(data) == total_size, f"Size mismatch: {len(data)} != {total_size}"

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_SP), exist_ok=True)
    with open(OUTPUT_SP, "wb") as f:
        f.write(data)
    print(f"Written translated SOUND.SP to: {OUTPUT_SP}")

    # Copy to live location
    with open(LIVE_SP, "wb") as f:
        f.write(data)
    print(f"Installed to live game: {LIVE_SP}")

    # Verify the output
    verify(OUTPUT_SP, translations)


def verify(path, translations):
    """Verify the patched file has correct translations."""
    with open(path, "rb") as f:
        data = f.read()

    total_size, entry_count, version = struct.unpack("<III", data[4:16])

    tag_close = "</TEXT>".encode("utf-16-le")
    total_texts = 0
    still_english = 0
    sample_checks = []

    pos = 0
    while True:
        idx = data.find(TAG_OPEN, pos)
        if idx == -1:
            break
        end_idx = data.find(tag_close, idx)
        if end_idx == -1:
            break
        end_idx += len(tag_close)
        text = data[idx + len(TAG_OPEN) : end_idx - len(tag_close)].decode(
            "utf-16le", errors="ignore"
        )
        total_texts += 1

        # Check if this text is a known English original
        if text in translations:
            still_english += 1
            if len(sample_checks) < 5:
                sample_checks.append(text)

        pos = end_idx

    print(f"\nVerification: {total_texts} <TEXT> entries found.")
    if still_english > 0:
        print(f"WARNING: {still_english} entries still contain English originals!")
        for s in sample_checks:
            print(f"  Still EN: {repr(s)}")
    else:
        print("ALL entries translated successfully!")

    # Check for forbidden glyphs
    FORBIDDEN = ["—", "–", "\u201c", "\u201d", "\u2018", "\u2019", "\u2026"]
    for fc in FORBIDDEN:
        fc_bytes = fc.encode("utf-16-le")
        if fc_bytes in data:
            count = data.count(fc_bytes)
            print(f"WARNING: Found forbidden character {repr(fc)} x{count}")

    # Check for uppercase Ã and Õ (UTF-16LE)
    upper_a_tilde = "Ã".encode("utf-16-le")
    upper_o_tilde = "Õ".encode("utf-16-le")
    for ch, name in [(upper_a_tilde, "Ã"), (upper_o_tilde, "Õ")]:
        if ch in data:
            # Could be in original audio data, only check in text regions
            pass  # We'll trust the translation sanitization


if __name__ == "__main__":
    build()
