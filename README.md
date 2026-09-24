# 🏎️ Driver: Parallel Lines — Tradução Integral para Português do Brasil (PT-BR)

[![Status](https://img.shields.io/badge/Status-100%25%20Completo-brightgreen.svg)](#)
[![Versão](https://img.shields.io/badge/Versão-2.0%20Final-blue.svg)](#)
[![Compatibilidade](https://img.shields.io/badge/Engine-PC%20(Steam%20%7C%20GOG%20%7C%20Retail)-red.svg)](#)
[![Plataforma](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux%20%7C%20Steam%20Deck-orange.svg)](#)
[![Nexus Mods](https://img.shields.io/badge/Nexus%20Mods-Mod%209-informational.svg)](https://www.nexusmods.com/driverparrallellines/mods/9)
[![Licença](https://img.shields.io/badge/Licen%C3%A7a-Gratuita%20(Fan--Made)-purple.svg)](#)

Tradução e localização integral, autêntica e tecnicamente homologada de **Driver: Parallel Lines** (versão de PC) para o **Português do Brasil (PT-BR)**.

> **Novidade da versão 2.0**: A histórica limitação técnica que deixava as legendas de diálogos *in-game* em inglês foi **100% superada** através da engenharia reversa do banco de áudio proprietário `Sounds/SOUND.SP` (162 MB) e dos containers de missão `LifeEvents/*.sp`!

---

## 👤 Créditos do Projeto

- **Idealização, Coordenação e Direção Geral**: **Romoaldo Cordeiro dos Santos Júnior** ([0neRim](https://github.com/0neRim))
- **Adaptação Cultural, Localização de Gírias e Linguagem de Época**: Romoaldo Cordeiro dos Santos Júnior
- **Engenharia Reversa dos Formatos Binários & Verificação de Integridade**: Desenvolvido com assistência de Pair Programming e Engenharia de Localização
- **Apoio e Comunidade**: Aos fãs e entusiastas de *Driver* no Brasil.

---

## 📥 Download Direto da Tradução

Para baixar o pacote pronto para instalação, faça o download do arquivo compactado:
👉 **[Baixar Driver_Parallel_Lines_PTBR_v2.0.zip](https://github.com/0neRim/driver-parallel-lines-pt-br/releases/download/v2.0/Driver_Parallel_Lines_PTBR_v2.0.zip)** *(Disponível também na aba [Releases](https://github.com/0neRim/driver-parallel-lines-pt-br/releases/tag/v2.0))*.

---

## 🌟 Destaques da Localização

### 1. 100% dos Textos Traduzidos (121 Arquivos Auditados)
- **Interface e Menus (UI - 8 arquivos)**: Menus principais, tela de opções, garagem de veículos, modificações/tunagem, telas de pausa (eras 70s e 2000s) e tutoriais.
- **Cutscenes e Filmes Narrativos (17 arquivos)**: Todas as cenas de história traduzidas, retratando a trajetória de TK desde 1978 até sua vingança em 2006.
- **Briefings de Missão (27 arquivos)**: Todas as instruções e conversas pré-missão com Slink, Ray, os mexicanos, The Colombian e contatos de rua.
- **Objetivos de Missão (34 arquivos)**: Notificações em tempo real na tela para missões principais, secundárias, corridas ilegais e agiotagem.
- **Scripts de Áudio, Tutoriais e Rádio (27 arquivos)**: Falas instrutivas, estações de rádio e diálogos dinâmicos de corrida.
- **Textos do Sistema (5 arquivos)**: Controles, nomes de carros, textos gerais de HUD, mensagens de rede e overlays.
- **Containers Binários LifeEvents (2 arquivos `.sp` — 3.093 entradas)**:
  - `LifeEvents/nyc_then_mission_text.sp` (1.593 entradas — Era 1978)
  - `LifeEvents/nyc_now_mission_text.sp` (1.500 entradas — Era 2006)
- **Banco de Áudio SOUND.SP (1 arquivo `.sp` — 692 legendas)**:
  - Legendas de diálogos falados durante o gameplay (perseguições policiais, insultos dos rivais, reações de pedestres e ordens de gangue).

---

### 2. Fidelidade Cultural e Linguística
- **Linguagem crua e sem censura**: Preservação total do tom visceral do jogo original (*porra, caralho, merda, filho da puta, desgraçado, vai tomar no cu*).
- **Diferenciação histórica de eras**:
  - **Era 1978**: Gírias clássicas dos anos 70/80 (*tiras, cana, grana, mina, bronca, trampo, bicho, dar o fora*).
  - **Era 2006**: Gírias contemporâneas de periferia e vingança (*os cana, fita, cagueta, traíra, colar junto*).
- **Adaptação de Personagens**:
  - `TK`: Mantido como *TK*.
  - `The Kid` / `Kid`: Adaptado como *Moleque* (tom provocativo e depreciativo dos inimigos) ou *Garoto* (usado pelo veterano Ray).
  - `Wheelman`: Adaptado como *Piloto de fuga*.

---

### 3. Rigor Técnico e Correção de Bugs da Engine
- **Codificação Perfeita**: Arquivos de texto compilados rigorosamente em **UTF-16 Little Endian com BOM (0xFF 0xFE)** e quebras de linha Windows CRLF (`\r\n`).
- **Correção do Bug de Glifos (□)**: A fonte original da engine não possui glifos para maiúsculas acentuadas como `Ã` e `Õ` (que causavam o famoso caractere de quadrado na palavra "Não"). Todos os textos foram perfeitamente higienizados para o charset nativo do jogo.
- **Reconstrução Binária Alinhada**: Containers binários `.sp` reconstruídos respeitando estritamente o alinhamento de setor de 2048 bytes da engine Reflections CHNK.
- **Preservação de Tokens**: Preservação exata de macros `#Macro`, glifos de controle (`$^A`, `&^A`) e formatadores (`%s`, `%d`).

---

## 📂 Estrutura do Repositório

```
driver-parallel-lines-traducao-ptbr/
├── LEIA-ME.txt                  # Manual completo e termos em texto puro
├── README.md                    # Documentação do projeto no GitHub
├── LICENSE                      # Licença de uso
├── .gitattributes               # Configuração para arquivos binários grandes (Git LFS)
├── FMV/                         # 78 arquivos (cutscenes, briefings e objetivos)
├── GUI/                         # 8 arquivos (menus e interface)
├── Music/                       # 27 arquivos (rádio, tutoriais e corridas)
├── Text/                        # 5 arquivos (controles, HUD e veículos)
├── LifeEvents/                  # 2 containers binários (.sp) com 3.093 missões
├── Sounds/                      # SOUND.SP com 692 legendas in-game (162 MB)
└── scripts/                     # Scripts de automação e rebuild técnico
    ├── patch_ptbr.py            # Utilitário CLI completo de aplicação/backup/verificação
    └── build_sound_sp.py        # Rebuilder binário do banco de áudio SOUND.SP
```

---

## 🎮 Instruções de Instalação

### Instalação Manual Direta:

1. Localize a pasta raiz onde o jogo está instalado no seu computador:
   - **Steam (Windows)**: `C:\Program Files (x86)\Steam\steamapps\common\Driver Parallel Lines\`
   - **GOG (Windows)**: `C:\GOG Games\Driver Parallel Lines\`
   - **Linux / Steam Deck (Heroic Games Launcher)**: `~/Games/Heroic/Driver Parallel Lines/`
   - **Linux / Steam Deck (Proton / Steam)**: `~/.local/share/Steam/steamapps/common/Driver Parallel Lines/`
2. *(Recomendado)* Faça uma cópia de segurança das pastas originais (`FMV`, `GUI`, `Music`, `Text`, `LifeEvents` e `Sounds/SOUND.SP`).
3. Copie as pastas `FMV`, `GUI`, `Music`, `Text`, `LifeEvents` e `Sounds` deste projeto e cole dentro da pasta raiz do jogo, confirmando a substituição dos arquivos existentes.
4. Execute o jogo e aproveite 100% em Português do Brasil!

---

## 💖 Apoie o Projeto

Se você gostou deste projeto e deseja incentivar novos trabalhos de localização de jogos clássicos para a nossa comunidade, considere apoiar via Pix:

- **Chave Aleatória Pix**:
  `196300c7-3421-4cbd-a45f-893ee12ed75f`
- **Nome**: Romoaldo Cordeiro dos Santos Júnior

---

## ⚖️ Termos de Uso e Isenção de Responsabilidade

Este é um projeto não-comercial criado por fãs e para fãs da franquia *Driver*. É terminantemente proibida a venda total ou parcial dos arquivos desta tradução.

*Driver: Parallel Lines* e todos os direitos associados são marcas comerciais e propriedades intelectuais da Ubisoft Entertainment / Reflections Interactive / Atari.
