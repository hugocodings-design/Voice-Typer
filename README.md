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
- [ ] System-tray icon with status (idle / recording / transcribing)
- [ ] Settings file / UI (model, language, hotkey, device)
- [ ] Voice-activity detection to trim silences
- [ ] Packaged `.exe` (PyInstaller) and start with Windows

## Requirements

- Windows 11
- Python **3.12** recommended (faster-whisper's native dependencies may not ship wheels for the newest Python yet)
- A microphone
- Optional: NVIDIA GPU + CUDA 12 / cuDNN 9 for faster transcription

## Run it

```powershell
cd "C:\Users\Hdasi\Desktop\PROJETS CLAUDE\VOICE TYPER"
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python -m voice_typer
```

The first run downloads the Whisper model (default `small`, ~460 MB) into the Hugging Face cache.
After that, everything works offline.

Hold `ctrl+alt+space`, talk, release. Press `ctrl+c` in the terminal to quit.

## Configuration

Settings live in [`voice_typer/config.py`](voice_typer/config.py) and can be overridden with environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `VT_MODEL` | `small` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3`, `distil-large-v3`… or a local folder path |
| `VT_LANGUAGE` | *(auto)* | Force a language, e.g. `fr` or `en` |
| `VT_DEVICE` | `cpu` | `cpu` or `cuda` |
| `VT_COMPUTE_TYPE` | `int8` | `int8`, `int8_float16`, `float16`… |
| `VT_HOTKEY` | `ctrl+alt+space` | Push-to-talk combination |
| `VT_OUTPUT` | `paste` | `paste` (clipboard + ctrl+v, fast and reliable) or `type` (simulated keystrokes) |

## Project layout

```
VOICE TYPER/
├── voice_typer/
│   ├── __main__.py     # entry point: python -m voice_typer
│   ├── app.py          # wires hotkey → recorder → transcriber → output
│   ├── config.py       # settings (env-var overridable)
│   ├── recorder.py     # microphone capture (sounddevice)
│   ├── transcriber.py  # faster-whisper wrapper
│   ├── output.py       # types / pastes text into the focused app
│   └── hotkey.py       # global push-to-talk hotkey
├── requirements.txt
└── CLAUDE.md
```
