# Voice Typer

Local, offline voice-to-text dictation for Windows 11 — in the spirit of [Handy](https://github.com/cjpais/Handy).

Hold a global hotkey, speak, release: your speech is transcribed **on your own machine** with Whisper
(via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) and typed into whatever app has focus.
No cloud API, no account, nothing leaves your PC.

## Features (MVP)

- [x] Push-to-talk global hotkey (default: `ctrl+alt+space`, hold to record)
- [x] Microphone capture at 16 kHz mono
- [x] Local transcription with faster-whisper (CPU int8 by default, CUDA optional)
- [x] Types the text into the focused window (or pastes it via the clipboard)
- [x] Desktop window with live status (ready / recording / transcribing)
- [x] French and English (plus auto-detect when you mix both)
- [x] Model manager: pick a model by speed vs. accuracy, download it in one click, switch without restarting
- [x] Import your own models: a local faster-whisper folder or a Hugging Face repo id
- [x] Settings saved between launches (`%APPDATA%\VoiceTyper\settings.json`)
- [x] Voice-activity detection to trim silences
- [x] Custom shortcut (record any combo, or pick F9 / Right Ctrl / Ctrl+Win…); its keys are swallowed so nothing leaks into the app
- [x] Two modes: hold to talk, or press once to start / once to stop
- [x] Floating indicator with a live mic level while dictating (never steals focus)
- [x] Icon next to the clock: closing the window keeps it running; option to start with Windows
- [x] Interface in French or English
- [x] Windows 11 look in bright green and gray (recoloured sv-ttk), light / dark / follow Windows, sidebar navigation, themed pop-ups
- [x] Personal dictionary: words passed to Whisper as `hotwords` + automatic replacements ("chat GPT" → "ChatGPT")
- [x] One-click French / English / auto switch on Home, in the tray menu and with a shortcut
- [x] Optional live typing: words appear at the cursor while you speak, the end is corrected on release
- [x] Right-click menus: models (use, download, delete from disk, open folder), history, dictionary
- [x] Dictation history (local, last 200), microphone choice + level test, start/stop sounds, optional trailing space
- [x] NVIDIA GPU acceleration, automatic with CPU fallback (RTX 2080 Super: ~0.25 s instead of ~5.5 s per sentence with large models)
- [x] **AI writing presets** — a local LLM rewrites the dictation before typing it (email with greeting,
      short paragraphs and signature; quick message; bullet notes; fix only; or your own), each preset with
      its own shortcut (F2, F3, F4…). Embedded in the app: no Ollama / LM Studio to install
- [x] Last dictation stays on the clipboard (Ctrl+V pastes it again) + optional shortcut to re-type it
      after a stray click (Home → "Recoller la dernière dictée")
- [x] **Esc cancels** a recording (nothing is typed), in both modes
- [x] **Voice commands** ("à la ligne", "nouveau paragraphe", "virgule", "ouvrir les guillemets"…),
      can be turned off; full list on the **Aide & commandes** page
- [x] Optional **live transcription** under the indicator while you speak (Réglages)
- [x] **Rewrite the selected text** with a preset via a shortcut, and **per-app presets**
      (e.g. Outlook → Courriel automatically)
- [x] Clipboard privacy: dictations are kept out of Windows clipboard history (Win+V) and cloud sync
- [x] Welcome assistant on first launch (language, model suited to the PC, mic test, shortcut)
- [x] Diagnostic export (zip without your personal texts) for troubleshooting
- [x] **Windows installer** (`VoiceTyperSetup-x.y.z.exe`, no admin rights) — see *Build the installer*

## Requirements

- Windows 11
- Python **3.12** recommended (faster-whisper's native dependencies may not ship wheels for the newest Python yet)
- A microphone
- Optional: an NVIDIA GPU (recent driver). No CUDA install needed: CTranslate2 bundles cuDNN and
  `requirements.txt` installs cuBLAS 12 inside the venv.

## Run it

```powershell
cd "C:\Users\Hdasi\Desktop\PROJETS CLAUDE\VOICE TYPER"
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python -m voice_typer
```

A window opens. The first run downloads the default model (`small`, ~480 MB) into the Hugging Face cache;
after that, everything works offline.

Hold `ctrl+alt+space` (or your own shortcut), talk, release. Closing the window keeps Voice Typer
running next to the clock; quit from the tray icon's menu or **Réglages → Quitter**.

Once the venv is set up, you can simply double-click **`Start Voice Typer.bat`** (no console window).

## Install (for colleagues)

Run `VoiceTyperSetup-x.y.z.exe`: no administrator rights, no Python, nothing else to install.
It installs into `%LOCALAPPDATA%\Programs\Voice Typer`, adds a Start-menu entry (optional desktop
shortcut and "start with Windows"), and the welcome assistant downloads the right models on first launch.
Uninstall from Windows Settings → Apps; it asks whether to also delete settings and downloaded models.
Windows SmartScreen may warn the first time ("unknown publisher", the installer isn't code-signed):
*More info → Run anyway*.

## Build the installer

One command, ~2–4 minutes (tests → PyInstaller → self-test of the built app → Inno Setup):

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1          # add -SkipTests to go faster
```

Output: `dist\VoiceTyperSetup-<version>.exe` (version from `voice_typer/__init__.py`).
One-time setup: `venv\Scripts\python.exe -m pip install pyinstaller` and
`winget install --id JRSoftware.InnoSetup -e --scope user`.
Models are not bundled (the installer stays ~0.5 GB, mostly NVIDIA cuBLAS for GPU acceleration).

## Publishing an update

Installed copies check `latest.json` on the public repository
[Voice-Typer-Releases](https://github.com/hugocodings-design/Voice-Typer-Releases) (installers only, no
source code) 20 s after start and every 6 h. When a newer version exists, a banner offers
**Installer maintenant / Plus tard / Ignorer cette version**. The installer is downloaded, its SHA-256
checked, then run silently with `/UPDATE=1`: settings, history and models are kept and the new version
restarts by itself. **Réglages → Mises à jour** can turn the check off or run it by hand.

To ship a change:

```powershell
# 1. bump __version__ in voice_typer/__init__.py
powershell -ExecutionPolicy Bypass -File installeruild.ps1
powershell -ExecutionPolicy Bypass -File installer\publish.ps1 -Notes "Ce qui change" -NotesEn "What changed"
```

`publish.ps1` needs the GitHub CLI logged in to the owner account. Protect that account with two-factor
authentication: whoever controls it can ship code to every installed copy.

## Reproducible install (pinned + hashed packages)

`requirements.lock` pins the exact version of every package (34) with its SHA-256 hashes: pip refuses
any file that differs from the one tested here (protects against a tampered or swapped package).

```powershell
python -m pip install --require-hashes --no-deps -r requirements.lock
```

## Using the window

- **Shortcut:** *Changer le raccourci…* records any combination (Esc cancels) or offers presets.
  Plain letters / Space alone are refused because they'd block normal typing.
- **Mode:** hold the keys while speaking, or press once to start and once to stop (auto-stops after 5 min).
- **Language you speak:** pick your language (faster and more accurate than Auto-detect). Takes effect immediately.
- **AI model:** select a model and click **Use this model** (or double-click). If it isn't on the PC yet,
  it asks before downloading. The current model keeps working until the new one is ready.

| Group | Model | Size | Best for |
|---|---|---|---|
| French | Français Distil (rapide) — `bofenghuang/whisper-large-v3-french-distil-dec2` | 1.5 GB | Fastest French-trained model |
| French | **Français Distil (précis)** — `…-french-distil-dec16` | 2.2 GB | Recommended for French |
| French | Français Large v3 — `bofenghuang/whisper-large-v3-french` | 3.1 GB | Most accurate French, slow on CPU |
| Multi | Tiny / Base / Small / Medium | 75 MB–1.5 GB | From instant to accurate |
| Multi | **Large v3 Turbo (compact)** — `Zoont/faster-whisper-large-v3-turbo-int8-ct2` | 810 MB | Recommended for French + English |
| Multi | Large v3 Turbo / Large v3 | 1.6 / 3.1 GB | Near-best / best multilingual |
| English | English Distil Small / Medium | 330 / 790 MB | Very fast English |
| English | **English Distil Large v3.5** | 1.5 GB | Recommended for English |

The French models are Whisper Large v3 fine-tuned on French by bofenghuang (MIT license); their
CTranslate2 files live in a `ctranslate2/` subfolder, written `repo#ctranslate2` in the catalog.

- **Import model folder…:** add a model already on disk. It must be in CTranslate2 format
  (folder containing `model.bin` + `config.json`, as published in `faster-whisper-…` repos).
- **Add from Hugging Face…:** add any CTranslate2 Whisper repo by id, e.g. `Systran/faster-whisper-large-v3`.
- **Remove:** removes an imported model from the list (files on disk are kept).

## AI writing (Écriture IA)

Hold a **preset shortcut** instead of the dictation shortcut: Whisper transcribes, then a small local
LLM rewrites the text following the preset's instructions, and the result is typed.

| Preset (default) | Shortcut | Result |
|---|---|---|
| Courriel / Email | F2 | "Bonjour Monsieur X," + 1–2 sentence paragraphs + closing + your signature |
| Message rapide / Quick message | F3 | Short, friendly chat message |
| Notes en points / Bullet notes | F4 | Bulleted list, one idea per line |
| Correction seule / Fix only | — | Grammar and punctuation only |

Edit, add, duplicate or delete presets (name, shortcut, free-text instructions; `{signature}` is
replaced by your signature) and try them without a microphone on the **Écriture IA** page.
Shortcuts of the same key can't be assigned twice; an assigned key (e.g. F2) is reserved for Voice Typer.

The LLM runs **inside** the app with CTranslate2 (the engine faster-whisper already uses): nothing else
to install, which is why it also works on locked-down work PCs. Models (downloaded once, then offline):

| Model | Size | Notes |
|---|---|---|
| `jncraton/Qwen2.5-1.5B-Instruct-ct2-int8` | 1.5 GB | Fast, fine for fixing / formatting (Apache 2.0) |
| **`jncraton/Qwen2.5-3B-Instruct-ct2-int8`** | 3.1 GB | Recommended — ~1 s per email on an RTX 2080 Super (Qwen research licence) |
| `jncraton/Qwen2.5-7B-Instruct-ct2-int8` | 7.6 GB | Smartest, needs a strong PC (Apache 2.0) |

On CPU only, expect several seconds per rewrite (1.5B is the best choice there).
If the rewrite fails, the raw transcript is typed so nothing is lost; the history keeps both versions.

## Power sharing (Partage de puissance)

One powerful PC (e.g. at home, with an NVIDIA card) can do the speech recognition and AI writing
for other devices running Voice Typer (e.g. a work laptop). Audio goes straight from one of your
PCs to the other: no cloud service is involved.

1. On the home PC: **Partage de puissance → Partager ce PC**, then **Copier le code** (`VT1-…`).
   The page shows how many devices are connected now (active in the last 10 min), in total, and a
   table per device (dictations, AI rewrites, minutes of audio).
2. On the other device: **Partage de puissance → Utiliser un autre PC**, paste the code, **Se connecter**.
3. From outside the home network, install [Tailscale](https://tailscale.com) (free) on both PCs with
   the same account and pick the `100.x.x.x` address before copying the code. No router setup needed,
   traffic is encrypted. On the same Wi-Fi the LAN address works without it.

If the home PC is off or unreachable, the client transcribes locally, so keep a model downloaded on it.
The home PC listens on TCP 8765 (`host_port`); Windows asks once to allow it on the network.
Every request needs the access key in the code; **Changer la clé d'accès** disconnects all devices.

## Advanced settings

**Réglages → Accélération** chooses Automatic (GPU if available), always GPU, or CPU only.
`%APPDATA%\VoiceTyper\settings.json` also holds `compute_type` (CPU, default `int8`) and
`gpu_compute_type` (GPU, default `float16`). Edit it while the app is closed.
"Start with Windows" writes a `VoiceTyper` value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

## Project layout

```
VOICE TYPER/
├── voice_typer/
│   ├── __main__.py     # entry point: python -m voice_typer
│   ├── app.py          # engine: hotkey → recorder → transcriber → output, events to the UI
│   ├── gui/            # tkinter window: window.py + pages/ (home, dictionary, models, writing,
│   │                   #   remote, help, settings), wizard.py (first run), shortcuts.py
│   ├── writer.py       # embedded LLM for AI-writing presets
│   ├── commands.py     # voice commands ("à la ligne", "virgule"…)
│   ├── clipboard.py    # Win32 clipboard with privacy flags (no history / cloud)
│   ├── winapp.py       # foreground app detection (per-app presets)
│   ├── remote.py       # power sharing: home-PC HTTP server, client, device counting
│   ├── updater.py      # automatic updates from the public releases repository
│   ├── diagnostic.py   # diagnostic zip export
│   ├── overlay.py      # floating "listening" pill (click-through, no focus)
│   ├── tray.py         # icon next to the clock (pystray)
│   ├── autostart.py    # start with Windows (HKCU Run key)
│   ├── i18n.py         # French / English interface texts
│   ├── models.py       # model catalog, download / import helpers, language list
│   ├── config.py       # settings saved as JSON in %APPDATA%\VoiceTyper
│   ├── recorder.py     # microphone capture (sounddevice)
│   ├── transcriber.py  # faster-whisper wrapper
│   ├── output.py       # types / pastes text into the focused app
│   └── hotkey.py       # global push-to-talk hotkey
├── installer/          # build.ps1, voice_typer.spec (PyInstaller), VoiceTyper.iss (Inno Setup), make_assets.py
├── tests/              # pytest (python -m pytest)
├── requirements.txt / requirements.lock
└── CLAUDE.md
```
