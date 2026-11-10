# Voice Typer — local offline dictation (Handy-like)

## What this project is
A Windows 11 desktop tool: hold a global hotkey, speak, release, and the speech is transcribed
locally with Whisper and typed into the focused application. **100 % local AI — no cloud APIs, ever.**
Separate project and repo from Speechify (`../SPEECHIFY HUGO`).

## Stack
- Python 3.12 (3.14 is installed system-wide, but faster-whisper's deps may lack wheels for it)
- faster-whisper (CTranslate2 Whisper) for speech-to-text, CPU int8 by default, CUDA optional
- sounddevice + numpy for 16 kHz mono mic capture
- keyboard for the global push-to-talk hotkey
- pyperclip + keyboard for output (clipboard paste or simulated typing)

## Layout
- `voice_typer/app.py` — orchestration: hotkey down → start recording; up → stop, transcribe in a worker thread, output text
- `voice_typer/config.py` — dataclass of settings, overridable with `VT_*` env vars
- `voice_typer/recorder.py`, `transcriber.py`, `output.py`, `hotkey.py` — one concern each

## Commands (PowerShell)
```powershell
venv\Scripts\activate
python -m voice_typer
```
Always run Python tools as `python -m <tool>` — `.exe` stubs (e.g. `uvicorn.exe`) are blocked on this machine.

## Conventions
- Never commit model files (`*.bin`, `*.gguf`, `models/`…) — see `.gitignore`.
- Keep the model loaded once at startup; transcription runs off the hotkey thread.
- Roadmap: tray icon, settings UI, VAD, PyInstaller `.exe`, autostart (see README).
