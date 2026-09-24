#!/usr/bin/env python3
"""
patch_ptbr.py - Driver: Parallel Lines (PC) Brazilian Portuguese Localization Manager

Manages backup, integrity verification, patch application, status reporting,
and restoration of original game localization files.

Supported Operations:
  --backup           Create pristine backup of all target localization files in backup_original/
  --apply [DIR]      Apply localized files from translations/ (or specified directory)
  --restore          Restore pristine original files from backup_original/
  --verify [DIR]     Verify encoding, BOM, CRLF, tags, and hash integrity of game/translation files
  --status           Show current installation state (ORIGINAL, TRANSLATED, MODIFIED)
  --dry-run          Simulate planned file operations without making any changes to disk
  --force            Force overwriting existing backup during --backup
  --verbose, -v      Enable detailed per-file output
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backup_original")
MANIFEST_SHA256 = "manifest_sha256.json"
MANIFEST_ORIGINAL = "manifest_original.json"
MANIFEST_INSTALLED = "manifest_installed.json"

TARGET_TEXT_DIRS = ["FMV", "GUI", "Text", "Music"]
TARGET_SP_CONTAINERS = [
    os.path.join("LifeEvents", "nyc_then_mission_text.sp"),
    os.path.join("LifeEvents", "nyc_now_mission_text.sp"),
    os.path.join("Sounds", "SOUND.SP"),
]

# Engine special tokens pattern: macros (#Macro), button glyphs ($^A, &^A), format specifiers (%s, %d)
TOKEN_REGEX = re.compile(r"(#[A-Za-z0-9_]+|[$&]\^[A-Za-z0-9]|%(?:[0-9]+)?[sdSc%])")


def norm_path(path: str) -> str:
    """Normalize path to forward-slash relative path."""
    return path.replace("\\", "/")


def compute_sha256(filepath: str) -> str:
    """Compute the SHA256 hexadecimal digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_target_files(base_dir: str = BASE_DIR) -> list:
    """
    Find all target localization files in the game installation.
    Returns sorted list of relative paths (using forward slashes).
    """
    targets = []
    for d in TARGET_TEXT_DIRS:
        dp = os.path.join(base_dir, d)
        if os.path.isdir(dp):
            for f in sorted(os.listdir(dp)):
                if f.lower().endswith(".txt"):
                    rel = norm_path(os.path.join(d, f))
                    targets.append(rel)

    for sp in TARGET_SP_CONTAINERS:
        sp_full = os.path.join(base_dir, sp)
        if os.path.exists(sp_full):
            targets.append(norm_path(sp))

    return sorted(targets)


def find_translation_files(trans_dir: str) -> list:
    """
    Find all translation files within a translations staging directory.
    Returns sorted list of relative paths.
    """
    if not os.path.isdir(trans_dir):
        return []
    trans_files = []
    for root, _, files in os.walk(trans_dir):
        for f in files:
            full_p = os.path.join(root, f)
            rel = norm_path(os.path.relpath(full_p, trans_dir))
            trans_files.append(rel)
    return sorted(trans_files)


def verify_text_file(filepath: str, original_filepath: str = None) -> tuple:
    """
    Verify a localization text file for:
      - UTF-16LE BOM (0xFF 0xFE)
      - Valid UTF-16LE decoding
      - CRLF line endings (tolerating known stock GUI header oddity)
      - XML-like <ID> and <TEXT> tags integrity and count parity
      - Format specifiers and button tokens preservation against original
    Returns: (is_valid: bool, errors: list, warnings: list)
    """
    errors = []
    warnings = []

    if not os.path.isfile(filepath):
        return False, [f"File not found: {filepath}"], warnings

    with open(filepath, "rb") as f:
        raw = f.read()

    # 1. BOM Check
    if not raw.startswith(b"\xff\xfe"):
        errors.append("Missing UTF-16LE BOM (must start with 0xFF 0xFE)")
        return False, errors, warnings

    # 2. UTF-16LE Decoding
    try:
        text = raw.decode("utf-16le")
    except UnicodeDecodeError as e:
        errors.append(f"Invalid UTF-16LE encoding: {e}")
        return False, errors, warnings

    # 3. CRLF Check
    cr_count = text.count("\r")
    lf_count = text.count("\n")
    crlf_count = text.count("\r\n")
    lone_lf = lf_count - crlf_count
    lone_cr = cr_count - crlf_count

    # Known stock exception: GUI/*.TXT files contain <PLATFORM>PC</PLATFORM>\n\r\n
    rel = norm_path(filepath)
    is_gui = "/gui/" in rel.lower() or rel.lower().startswith("gui/")
    if is_gui and lone_lf == 1:
        # Expected stock GUI header pattern
        pass
    elif lone_lf > 0:
        errors.append(f"Contains {lone_lf} lone LF (\\n) line endings without CR")
    if lone_cr > 0:
        errors.append(f"Contains {lone_cr} lone CR (\\r) line endings without LF")

    # 4. XML-like tag checks
    id_matches = list(re.finditer(r"<ID>(\d+)</ID>", text))
    text_matches = list(re.finditer(r"<TEXT>(.*?)</TEXT>", text, re.DOTALL))

    if len(id_matches) != len(text_matches):
        errors.append(
            f"Tag count mismatch: {len(id_matches)} <ID> tags vs {len(text_matches)} <TEXT> tags"
        )

    seen_ids = set()
    for m in id_matches:
        tag_val = m.group(1)
        if tag_val in seen_ids:
            errors.append(f"Duplicate <ID>{tag_val}</ID> tag detected")
        seen_ids.add(tag_val)

    # 5. Parity check against original if available
    if original_filepath and os.path.isfile(original_filepath):
        try:
            with open(original_filepath, "rb") as orig_f:
                orig_raw = orig_f.read()
            orig_text = orig_raw.decode("utf-16le", errors="replace")

            # Check ID parity
            orig_ids = [m.group(1) for m in re.finditer(r"<ID>(\d+)</ID>", orig_text)]
            curr_ids = [m.group(1) for m in id_matches]
            if orig_ids != curr_ids:
                errors.append(
                    f"ID sequence mismatch with original: expected {len(orig_ids)} IDs, got {len(curr_ids)} IDs"
                )

            # Check token preservation
            orig_tokens = TOKEN_REGEX.findall(orig_text)
            curr_tokens = TOKEN_REGEX.findall(text)
            if orig_tokens != curr_tokens:
                missing = [t for t in orig_tokens if t not in curr_tokens]
                if missing:
                    errors.append(f"Missing required tokens from original: {set(missing)}")
        except Exception as e:
            warnings.append(f"Could not compare with original {original_filepath}: {e}")

    return len(errors) == 0, errors, warnings


def verify_sp_file(filepath: str, expected_sha256: str = None) -> tuple:
    """
    Verify a .sp container file (binary CHNK format).
    Returns: (is_valid: bool, errors: list, warnings: list)
    """
    errors = []
    warnings = []

    if not os.path.isfile(filepath):
        return False, [f"File not found: {filepath}"], warnings

    size = os.path.getsize(filepath)
    if size == 0:
        errors.append("File is empty (0 bytes)")
        return False, errors, warnings

    with open(filepath, "rb") as f:
        header = f.read(4)
    if header != b"CHNK":
        errors.append(f"Invalid container header (expected b'CHNK', got {repr(header)})")

    if expected_sha256:
        actual_sha256 = compute_sha256(filepath)
        if isinstance(expected_sha256, (list, tuple, set)):
            matched = any(actual_sha256.lower() == exp.lower() for exp in expected_sha256 if exp)
            if not matched:
                errors.append(f"SHA256 hash mismatch: got {actual_sha256}, expected one of {expected_sha256}")
        elif actual_sha256.lower() != expected_sha256.lower():
            errors.append(f"SHA256 hash mismatch: expected {expected_sha256}, got {actual_sha256}")

    return len(errors) == 0, errors, warnings


def load_manifest(manifest_path: str) -> dict:
    """Load and return manifest dictionary."""
    if not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def is_backup_valid(backup_dir: str = BACKUP_DIR) -> tuple:
    """
    Check if the backup in backup_dir exists, has a valid manifest,
    and all backed up files exist and match their SHA256 hashes.
    Returns: (is_valid: bool, reason: str, manifest: dict)
    """
    if not os.path.isdir(backup_dir):
        return False, f"Backup directory does not exist: {backup_dir}", {}

    manifest_file = os.path.join(backup_dir, MANIFEST_SHA256)
    if not os.path.isfile(manifest_file):
        manifest_file = os.path.join(backup_dir, MANIFEST_ORIGINAL)
    if not os.path.isfile(manifest_file):
        return False, f"Manifest not found in {backup_dir}", {}

    manifest = load_manifest(manifest_file)
    files = manifest.get("files", {})
    if not files:
        return False, "Manifest contains no file entries", manifest

    for rel_path, meta in files.items():
        backup_file = os.path.join(backup_dir, rel_path)
        if not os.path.isfile(backup_file):
            return False, f"Missing backed up file: {rel_path}", manifest
        expected_hash = meta.get("sha256")
        if expected_hash:
            actual_hash = compute_sha256(backup_file)
            if actual_hash.lower() != expected_hash.lower():
                return False, f"Hash mismatch in backup for {rel_path}", manifest

    return True, f"Backup valid ({len(files)} files checked)", manifest


def do_backup(dry_run: bool = False, force: bool = False, verbose: bool = False) -> int:
    """
    Scan all target localization files and copy them into backup_original/,
    generating manifest_sha256.json and manifest_original.json.
    """
    print("=" * 60)
    print("Driver: Parallel Lines - Backup Operation")
    print("=" * 60)

    if not force and not dry_run:
        valid, reason, _ = is_backup_valid(BACKUP_DIR)
        if valid:
            print(f"Valid backup already exists in '{os.path.relpath(BACKUP_DIR, BASE_DIR)}':")
            print(f"  {reason}")
            print("Use --force if you wish to overwrite the existing backup.")
            return 0

    target_files = find_target_files(BASE_DIR)
    if not target_files:
        print("ERROR: No target localization files found in game directory!")
        return 1

    print(f"Scanning target localization files: {len(target_files)} files identified.")
    total_size = 0
    file_manifest = {}

    for rel_path in target_files:
        src = os.path.join(BASE_DIR, rel_path)
        size = os.path.getsize(src)
        total_size += size
        sha256 = compute_sha256(src)
        file_manifest[rel_path] = {
            "size": size,
            "sha256": sha256,
        }
        if verbose:
            print(f"  [TARGET] {rel_path} ({size} bytes, sha256={sha256[:12]}...)")

    print(f"Total target files: {len(target_files)} ({total_size / 1024:.1f} KB)")

    if dry_run:
        print("\n[DRY-RUN] No files were copied.")
        print(f"[DRY-RUN] Planned destination: {BACKUP_DIR}")
        print(f"[DRY-RUN] Planned manifest: {os.path.join(BACKUP_DIR, MANIFEST_SHA256)}")
        print("[DRY-RUN] Operation completed successfully in simulation mode.")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)

    copied_count = 0
    for rel_path in target_files:
        src = os.path.join(BASE_DIR, rel_path)
        dst = os.path.join(BACKUP_DIR, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied_count += 1
        if verbose:
            print(f"  [BACKUP] Copied -> {os.path.relpath(dst, BASE_DIR)}")

    manifest_data = {
        "version": "1.0",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "game_title": "Driver: Parallel Lines (PC)",
        "total_files": len(file_manifest),
        "files": file_manifest,
    }

    manifest_path_sha = os.path.join(BACKUP_DIR, MANIFEST_SHA256)
    manifest_path_orig = os.path.join(BACKUP_DIR, MANIFEST_ORIGINAL)

    with open(manifest_path_sha, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    shutil.copyfile(manifest_path_sha, manifest_path_orig)

    print(f"\nSuccessfully backed up {copied_count} files to '{os.path.relpath(BACKUP_DIR, BASE_DIR)}'.")
    print(f"Manifest written: {os.path.relpath(manifest_path_sha, BASE_DIR)}")
    return 0


def do_restore(dry_run: bool = False, verbose: bool = False) -> int:
    """
    Restore all pristine original files from backup_original/ into the game directories,
    validating against manifest_sha256.json.
    """
    print("=" * 60)
    print("Driver: Parallel Lines - Restore Operation")
    print("=" * 60)

    valid, reason, manifest = is_backup_valid(BACKUP_DIR)
    if not valid:
        print(f"ERROR: Cannot restore - {reason}")
        print("Please ensure a valid backup exists in 'backup_original/' before restoring.")
        return 1

    files = manifest.get("files", {})
    print(f"Restoring {len(files)} pristine files from backup...")

    if dry_run:
        print("\n[DRY-RUN] No files were restored.")
        for rel_path in sorted(files.keys()):
            if verbose:
                print(f"  [DRY-RUN RESTORE] Would copy: backup_original/{rel_path} -> {rel_path}")
        print(f"[DRY-RUN] Would restore {len(files)} files to game directories.")
        print("[DRY-RUN] Operation completed successfully in simulation mode.")
        return 0

    restored_count = 0
    for rel_path, meta in sorted(files.items()):
        src = os.path.join(BACKUP_DIR, rel_path)
        dst = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

        actual_sha = compute_sha256(dst)
        expected_sha = meta.get("sha256")
        if expected_sha and actual_sha.lower() != expected_sha.lower():
            print(f"ERROR: Hash verification failed after restoring {rel_path}!")
            return 1

        restored_count += 1
        if verbose:
            print(f"  [RESTORED] {rel_path} (verified SHA256)")

    # Clean up installed manifest if present
    installed_p = os.path.join(BASE_DIR, MANIFEST_INSTALLED)
    if os.path.isfile(installed_p):
        os.remove(installed_p)

    print(f"\nRestoration complete: {restored_count} files restored to pristine original state.")
    return 0


def do_apply(trans_dir: str = "translations", dry_run: bool = False, verbose: bool = False) -> int:
    """
    Apply translated files from translations/ (or specified directory) into
    the actual game directories, ensuring backup exists beforehand.
    """
    print("=" * 60)
    print("Driver: Parallel Lines - Apply Translation Operation")
    print("=" * 60)

    # 1. Ensure backup exists
    valid, reason, _ = is_backup_valid(BACKUP_DIR)
    if not valid:
        print("Notice: No valid backup detected. Creating automatic baseline backup first...")
        ret = do_backup(dry_run=dry_run, verbose=verbose)
        if ret != 0:
            print("ERROR: Automatic backup failed. Aborting translation application.")
            return ret

    trans_full = os.path.join(BASE_DIR, trans_dir) if not os.path.isabs(trans_dir) else trans_dir
    if not os.path.isdir(trans_full):
        print(f"Notice: Translations directory '{trans_dir}' does not exist or has no files.")
        print("Staged files are needed under 'translations/' to apply a translation.")
        return 0

    trans_files = find_translation_files(trans_full)
    if not trans_files:
        print(f"Notice: No translation files found in '{trans_dir}'.")
        return 0

    print(f"Found {len(trans_files)} translated file(s) in '{trans_dir}'.")

    # 2. Pre-flight verification of all translation files
    verification_failed = False
    for rel_path in trans_files:
        src = os.path.join(trans_full, rel_path)
        orig = os.path.join(BACKUP_DIR, rel_path)
        if not os.path.exists(orig):
            orig = os.path.join(BASE_DIR, rel_path)

        if rel_path.lower().endswith(".txt"):
            is_valid, errors, _ = verify_text_file(src, orig if os.path.exists(orig) else None)
            if not is_valid:
                verification_failed = True
                print(f"ERROR in translation file '{rel_path}':")
                for err in errors:
                    print(f"  - {err}")
        elif rel_path.lower().endswith(".sp"):
            is_valid, errors, _ = verify_sp_file(src)
            if not is_valid:
                verification_failed = True
                print(f"ERROR in translation container '{rel_path}':")
                for err in errors:
                    print(f"  - {err}")

    if verification_failed:
        print("\nERROR: Pre-flight integrity verification failed for translation files.")
        print("No files were applied. Please fix the errors listed above.")
        return 1

    if dry_run:
        print("\n[DRY-RUN] Pre-flight verification PASSED.")
        print(f"[DRY-RUN] Planned application: {len(trans_files)} files from '{trans_dir}' -> game root")
        for rel_path in trans_files:
            if verbose:
                print(f"  [DRY-RUN APPLY] Would copy: {trans_dir}/{rel_path} -> {rel_path}")
        print("[DRY-RUN] Operation completed successfully in simulation mode.")
        return 0

    # 3. Apply files
    applied_manifest = {}
    applied_count = 0
    for rel_path in trans_files:
        src = os.path.join(trans_full, rel_path)
        dst = os.path.join(BASE_DIR, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        applied_count += 1
        size = os.path.getsize(dst)
        sha = compute_sha256(dst)
        applied_manifest[rel_path] = {"size": size, "sha256": sha}
        if verbose:
            print(f"  [APPLIED] {rel_path} ({size} bytes, sha256={sha[:12]}...)")

    # Record installed manifest
    inst_data = {
        "version": "1.0",
        "applied_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_dir": trans_dir,
        "total_files": len(applied_manifest),
        "files": applied_manifest,
    }
    with open(os.path.join(BASE_DIR, MANIFEST_INSTALLED), "w", encoding="utf-8") as f:
        json.dump(inst_data, f, indent=2, ensure_ascii=False)

    print(f"\nTranslation applied successfully: {applied_count} files updated.")
    print(f"Recorded installed manifest: {MANIFEST_INSTALLED}")
    return 0


def do_verify(target_dir: str = None, verbose: bool = False) -> int:
    """
    Check the integrity of target localization files or translated files:
      - UTF-16LE encoding
      - BOM (0xFF 0xFE)
      - CRLF line endings
      - <ID> tags syntax, count parity, uniqueness
      - SHA256 against manifest if available
    """
    print("=" * 60)
    print("Driver: Parallel Lines - File Integrity Verification")
    print("=" * 60)

    files_to_check = []
    base_check_dir = BASE_DIR
    if target_dir:
        base_check_dir = os.path.join(BASE_DIR, target_dir) if not os.path.isabs(target_dir) else target_dir
        if not os.path.isdir(base_check_dir):
            print(f"ERROR: Specified directory does not exist: {target_dir}")
            return 1
        files_to_check = find_translation_files(base_check_dir)
        print(f"Verifying {len(files_to_check)} files in '{target_dir}'...")
    else:
        files_to_check = find_target_files(BASE_DIR)
        print(f"Verifying {len(files_to_check)} target files in game installation...")

    if not files_to_check:
        print("No files found to verify.")
        return 0

    # Load original manifest for reference if available
    orig_manifest_path = os.path.join(BACKUP_DIR, MANIFEST_SHA256)
    if not os.path.isfile(orig_manifest_path):
        orig_manifest_path = os.path.join(BACKUP_DIR, MANIFEST_ORIGINAL)
    orig_manifest = load_manifest(orig_manifest_path).get("files", {})

    inst_manifest_path = os.path.join(BASE_DIR, MANIFEST_INSTALLED)
    inst_manifest = load_manifest(inst_manifest_path).get("files", {}) if os.path.isfile(inst_manifest_path) else {}

    total_checked = 0
    passed_count = 0
    failed_count = 0
    issues = []

    for rel_path in files_to_check:
        total_checked += 1
        full_path = os.path.join(base_check_dir, rel_path)
        orig_path = os.path.join(BACKUP_DIR, rel_path) if os.path.exists(os.path.join(BACKUP_DIR, rel_path)) else os.path.join(BASE_DIR, rel_path)

        if rel_path.lower().endswith(".txt"):
            is_valid, errors, warnings = verify_text_file(
                full_path, orig_path if os.path.isfile(orig_path) and orig_path != full_path else None
            )
        elif rel_path.lower().endswith(".sp"):
            if not target_dir:
                valid_hashes = set()
                if inst_manifest and rel_path in inst_manifest:
                    valid_hashes.add(inst_manifest[rel_path].get("sha256"))
                if orig_manifest and rel_path in orig_manifest:
                    valid_hashes.add(orig_manifest[rel_path].get("sha256"))
                valid_hashes.discard(None)
                is_valid, errors, warnings = verify_sp_file(full_path, valid_hashes if valid_hashes else None)
            else:
                is_valid, errors, warnings = verify_sp_file(full_path, None)
        else:
            is_valid, errors, warnings = True, [], []

        if is_valid:
            passed_count += 1
            if verbose:
                print(f"  [PASS] {rel_path}")
        else:
            failed_count += 1
            issues.append((rel_path, errors))
            print(f"  [FAIL] {rel_path}")
            for err in errors:
                print(f"         ERROR: {err}")
        for w in warnings:
            if verbose:
                print(f"         WARN: {w}")

    print("\n" + "-" * 60)
    print(f"Verification Results: {passed_count}/{total_checked} PASSED, {failed_count} FAILED.")
    print("-" * 60)

    if failed_count > 0:
        print(f"ERROR: Integrity verification encountered {failed_count} failure(s).")
        return 1

    print("SUCCESS: All verified files strictly conform to engine specifications.")
    return 0


def do_status(verbose: bool = False) -> int:
    """
    Display current installation state:
      - ORIGINAL (Stock): 100% of files match original backup manifest hashes
      - PT-BR LOCALIZED: files match installed translation manifest hashes
      - MODIFIED / UNRECOGNIZED: files differ from known states
    """
    print("=" * 60)
    print("Driver: Parallel Lines - Installation Status")
    print("=" * 60)

    # 1. Backup Status
    valid_backup, reason_backup, orig_manifest = is_backup_valid(BACKUP_DIR)
    orig_files = orig_manifest.get("files", {})
    print(f"Backup Status: {'VALID (' + str(len(orig_files)) + ' files)' if valid_backup else 'MISSING / INCOMPLETE'}")
    if not valid_backup:
        print(f"  Details: {reason_backup}")

    # 2. Installed Translations Manifest
    inst_manifest_path = os.path.join(BASE_DIR, MANIFEST_INSTALLED)
    inst_manifest = load_manifest(inst_manifest_path).get("files", {})

    target_files = find_target_files(BASE_DIR)
    if not target_files:
        print("ERROR: Target localization files not found in game directory!")
        return 1

    matched_original = 0
    matched_translated = 0
    modified_or_unknown = 0

    status_details = []

    for rel_path in target_files:
        full_p = os.path.join(BASE_DIR, rel_path)
        cur_hash = compute_sha256(full_p)
        orig_hash = orig_files.get(rel_path, {}).get("sha256")
        inst_hash = inst_manifest.get(rel_path, {}).get("sha256")

        if orig_hash and cur_hash.lower() == orig_hash.lower():
            state = "ORIGINAL"
            matched_original += 1
        elif inst_hash and cur_hash.lower() == inst_hash.lower():
            state = "TRANSLATED"
            matched_translated += 1
        elif not orig_hash and not inst_hash:
            state = "UNCHECKED (No Manifest)"
            modified_or_unknown += 1
        else:
            state = "MODIFIED"
            modified_or_unknown += 1

        status_details.append((rel_path, state))
        if verbose:
            print(f"  [{state}] {rel_path}")

    # Summary
    total = len(target_files)
    print("\nFile State Summary:")
    print(f"  Original (Stock)   : {matched_original:3d} / {total}")
    print(f"  Translated (PT-BR) : {matched_translated:3d} / {total}")
    print(f"  Modified / Other   : {modified_or_unknown:3d} / {total}")

    print("\nOverall System State:")
    if valid_backup and matched_original == total:
        print("  >> ORIGINAL (Stock) - Pristine factory installation.")
    elif matched_translated > 0 and modified_or_unknown == 0:
        if matched_translated == total:
            print("  >> PT-BR LOCALIZED (Active) - 100% Brazilian Portuguese translation active.")
        else:
            print(f"  >> PARTIAL PT-BR - {matched_translated}/{total} files localized, remainder stock.")
    elif modified_or_unknown > 0:
        print(f"  >> MODIFIED / UNRECOGNIZED - {modified_or_unknown} file(s) differ from known baselines.")
    else:
        print("  >> BASELINE STOCK - Target files present, backup recommended.")

    print("=" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Driver: Parallel Lines (PC) Brazilian Portuguese Localization Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--backup",
        action="store_true",
        help="Scan and copy all original target localization files into backup_original/ with manifest",
    )
    parser.add_argument(
        "--apply",
        nargs="?",
        const="translations",
        default=None,
        metavar="DIR",
        help="Apply translated files from translations/ (or DIR) into actual game directories",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore all pristine original files from backup_original/ into game directories",
    )
    parser.add_argument(
        "--verify",
        nargs="?",
        const="",
        default=None,
        metavar="DIR",
        help="Check UTF-16LE, BOM, CRLF, tags, and hash integrity of game or translation files",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display current installation state (ORIGINAL, TRANSLATED, MODIFIED)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate planned operations without modifying any files on disk",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing backup in backup_original/ during --backup",
    )
    parser.add_argument(
        "--dir",
        dest="custom_dir",
        default=None,
        metavar="DIR",
        help="Specify custom directory for verification or translation source",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display detailed per-file output during operations",
    )

    args = parser.parse_args()

    # Route actions
    has_action = False

    if args.backup:
        has_action = True
        sys.exit(do_backup(dry_run=args.dry_run, force=args.force, verbose=args.verbose))

    if args.apply is not None:
        has_action = True
        target_dir = args.custom_dir if args.custom_dir else args.apply
        sys.exit(do_apply(trans_dir=target_dir, dry_run=args.dry_run, verbose=args.verbose))

    if args.restore:
        has_action = True
        sys.exit(do_restore(dry_run=args.dry_run, verbose=args.verbose))

    if args.verify is not None:
        has_action = True
        verify_target = args.custom_dir if args.custom_dir else (args.verify if args.verify != "" else None)
        sys.exit(do_verify(target_dir=verify_target, verbose=args.verbose))

    if args.status:
        has_action = True
        sys.exit(do_status(verbose=args.verbose))

    if args.dry_run and not has_action:
        print("[DRY-RUN] Simulation mode active. No operation specified.")
        print("Use --dry-run with --backup, --apply, or --restore to simulate file actions.")
        print()
        sys.exit(do_status(verbose=args.verbose))

    # Default if no arguments provided: print help and current status
    parser.print_help()
    print()
    sys.exit(do_status(verbose=args.verbose))


if __name__ == "__main__":
    main()
