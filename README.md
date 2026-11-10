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
- [x] Language picker (Auto-detect, Français, English, Español… ~20 languages)
- [x] Model manager: pick a model by speed vs. accuracy, download it in one click, switch without restarting
- [x] Import your own models: a local faster-whisper folder or a Hugging Face repo id
- [x] Settings saved between launches (`%APPDATA%\VoiceTyper\settings.json`)
- [x] Voice-activity detection to trim silences
- [x] Custom shortcut (record any combo, or pick F9 / Right Ctrl / Ctrl+Win…); its keys are swallowed so nothing leaks into the app
- [x] Two modes: hold to talk, or press once to start / once to stop
- [x] Floating indicator with a live mic level while dictating (never steals focus)
- [x] Icon next to the clock: closing the window keeps it running; option to start with Windows
- [x] Interface in French or English
- [x] Windows 11 look (sv-ttk), light / dark / follow Windows, sidebar navigation
- [x] Personal dictionary: words passed to Whisper as `hotwords` + automatic replacements ("chat GPT" → "ChatGPT")
- [x] All ~100 Whisper languages, favorites, one-click switch on Home, in the tray menu and with a shortcut
- [x] Right-click menus: models (use, download, delete from disk, open folder, Hugging Face page), languages, history, dictionary
- [x] Dictation history (local, last 200), microphone choice + level test, start/stop sounds, optional trailing space
- [x] NVIDIA GPU acceleration, automatic with CPU fallback (RTX 2080 Super: ~0.25 s instead of ~5.5 s per sentence with large models)
- [ ] Packaged `.exe`
- [ ] Packaged `.exe` (PyInstaller) and start with Windows

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
│   ├── gui.py          # tkinter window: Accueil / Modèles IA / Réglages tabs
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
├── requirements.txt
└── CLAUDE.md
```
