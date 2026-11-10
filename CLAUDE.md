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

- tkinter (stdlib) for the desktop window — no extra UI dependency

## Layout
- `voice_typer/app.py` — `Engine`: hotkey down → record; up → transcribe in a worker thread, output text. Reports to the UI only via `engine.events` (a queue)
- `voice_typer/gui.py` — tkinter window polling `engine.events`; never call tkinter from worker threads
- `voice_typer/models.py` — model catalog (speed/accuracy), language list, download/import helpers
- `voice_typer/config.py` — settings dataclass saved to `%APPDATA%\VoiceTyper\settings.json`
- `voice_typer/recorder.py`, `transcriber.py`, `output.py`, `hotkey.py` — one concern each

## Commands (PowerShell)
```powershell
venv\Scripts\activate
python -m voice_typer
```
Always run Python tools as `python -m <tool>` — `.exe` stubs (e.g. `uvicorn.exe`) are blocked on this machine.

## Conventions
- Never commit model files (`*.bin`, `*.gguf`, `models/`…) — see `.gitignore`.
- Model switching loads the new model in the background and swaps only on success (old model keeps working).
- Imported models must be CTranslate2 format (`model.bin` + `config.json`) or a HF repo id.
- Roadmap: tray icon, hotkey/GPU choice in the UI, PyInstaller `.exe`, autostart (see README).
