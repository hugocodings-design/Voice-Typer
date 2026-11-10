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
- `voice_typer/hotkey.py` — suppressing low-level hook: the trigger key is swallowed while the combo is held; a mask key (VK 0xE8) stops Alt/Win from opening menus. Callbacks run on a worker thread (hooks must return fast)
- `voice_typer/overlay.py` — click-through, non-activating pill; shown/hidden via opacity (re-showing a window can steal focus)
- `voice_typer/tray.py`, `autostart.py`, `i18n.py` — tray icon, HKCU Run autostart, FR/EN strings (every UI text goes through `tr()`)
- `run.pyw` — under pythonw `sys.stdout/stderr` are None: it redirects them to `%APPDATA%\VoiceTyper\voice_typer.log` (tracebacks land there) and disables HF progress bars, which otherwise crash downloads/loads (`'NoneType' object has no attribute 'write'`). Test console-less behaviour with pythonw, not python
- `run.pyw` — console-less entry used by `Start Voice Typer.bat` and autostart (`--minimized` starts in the tray)
- Single instance enforced with a named mutex (two instances would type everything twice)
- `voice_typer/gpu.py` — adds `site-packages/nvidia/*/bin` (cuBLAS 12 from `nvidia-cublas-cu12`) to the DLL search path; must run before CTranslate2 uses CUDA (done at `transcriber.py` import). `Transcriber` tries CUDA float16 with a warm-up, falls back to CPU int8 and reports `gpu_error`
- `voice_typer/gui.py` — sidebar + pages (home, dictionary, languages, models, settings); `_build()` rebuilds everything (theme/UI-language change). `ui_theme.py` = sv-ttk + palettes + Segoe Fluent icon glyphs
- `voice_typer/dictionary.py` — vocabulary → faster-whisper `hotwords`; replacements = case-insensitive whole-phrase regex after transcription
- `voice_typer/languages.py` — all Whisper languages (FR/EN names); favorites in `config.favorite_languages`, cycled by `config.language_hotkey`
- History lives in `%APPDATA%\VoiceTyper\history.json` (separate from settings)
- Microphones are listed/opened through the DirectSound host API (MME truncates names)
- Dev machine: RTX 2080 Super 8 GB — GPU makes large models ~20× faster than CPU
- `voice_typer/recorder.py`, `transcriber.py`, `output.py`, `hotkey.py` — one concern each
- `voice_typer/writer.py` — AI writing presets: embedded LLM (CTranslate2 `Generator` + `tokenizers`, Qwen 2.5 Instruct int8, manual ChatML prompt with one few-shot example). **No Ollama / server software** — the user installs this on a work PC too. `Engine` keeps one `Hotkey` per preset (`config.presets`: id/name/hotkey/instructions, `None` = defaults), records with `_active_preset`, then `rewrite()`; on failure the raw text is typed. `writer_preload` keeps the LLM in memory
- Hotkey conflicts (dictation / language / presets) are checked in `gui._taken_hotkeys`

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
- The user speaks French: default UI language is `fr`.
- Roadmap: PyInstaller `.exe` (see README).
