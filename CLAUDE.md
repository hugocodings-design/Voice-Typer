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
- `clipboard.py` (ctypes Win32, privacy formats so dictations skip Win+V history / cloud) + keyboard for output

- tkinter (stdlib) for the desktop window — no extra UI dependency

## Layout
- `voice_typer/app.py` — `Engine`: hotkey down → record; up → transcribe in a worker thread, output text. Reports to the UI only via `engine.events` (a queue)
- `voice_typer/gui/` — tkinter window polling `engine.events`; never call tkinter from worker threads. `window.py` = `Window` built from page mixins (`pages/*.py`), `wizard.py` (first-run assistant, `config.first_run_done`), `shortcuts.py` (recorder + conflict check `_taken_hotkeys`)
- `voice_typer/models.py` — model catalog (speed/accuracy), language list, download/import helpers
- `voice_typer/config.py` — settings dataclass saved to `%APPDATA%\VoiceTyper\settings.json`
- `voice_typer/hotkey.py` — suppressing low-level hook: the trigger key is swallowed while the combo is held; a mask key (VK 0xE8) stops Alt/Win from opening menus. Callbacks run on a worker thread (hooks must return fast)
- `voice_typer/overlay.py` — click-through, non-activating pill; shown/hidden via opacity (re-showing a window can steal focus)
- `voice_typer/tray.py`, `autostart.py`, `i18n.py` — tray icon, HKCU Run autostart, FR/EN strings (every UI text goes through `tr()`)
- `run.pyw` — under pythonw `sys.stdout/stderr` are None: it redirects them to `%APPDATA%\VoiceTyper\voice_typer.log` (tracebacks land there) and disables HF progress bars, which otherwise crash downloads/loads (`'NoneType' object has no attribute 'write'`). Test console-less behaviour with pythonw, not python
- `run.pyw` — console-less entry used by `Start Voice Typer.bat` and autostart (`--minimized` starts in the tray)
- Single instance enforced with a named mutex (two instances would type everything twice)
- `voice_typer/gpu.py` — adds `site-packages/nvidia/*/bin` (cuBLAS 12 from `nvidia-cublas-cu12`) to the DLL search path; must run before CTranslate2 uses CUDA (done at `transcriber.py` import). `Transcriber` tries CUDA float16 with a warm-up, falls back to CPU int8 and reports `gpu_error`
- `_build()` rebuilds every page (theme/UI-language change) but keeps Toplevels (overlay caption, assistant). `ui_theme.py` = sv-ttk + palettes + Segoe Fluent icon glyphs
- `voice_typer/dictionary.py` — vocabulary → faster-whisper `hotwords`; replacements = case-insensitive whole-phrase regex after transcription
- `voice_typer/languages.py` — French and English only (`SUPPORTED`; the user's models are multilingual or FR/EN specialists, so no Languages page). `config.language` is None (auto) / fr / en, forced on load; `config.language_hotkey` toggles FR ↔ EN (set on Home). The full list only names old history entries
- History lives in `%APPDATA%\VoiceTyper\history.json` (separate from settings)
- Microphones are listed/opened through the DirectSound host API (MME truncates names)
- Dev machine: RTX 2080 Super 8 GB — GPU makes large models ~20× faster than CPU
- `voice_typer/recorder.py`, `transcriber.py`, `output.py`, `hotkey.py` — one concern each
- `voice_typer/writer.py` — AI writing presets: embedded LLM (CTranslate2 `Generator` + `tokenizers`, Qwen 2.5 Instruct int8, manual ChatML prompt with one few-shot example). **No Ollama / server software** — the user installs this on a work PC too. `Engine` keeps one `Hotkey` per preset (`config.presets`: id/name/hotkey/instructions, `None` = defaults), records with `_active_preset`, then `rewrite()`; on failure the raw text is typed. `writer_preload` keeps the LLM in memory
- `remote.py` — power sharing between PCs. `config.remote_mode` off/host/client. Host = `ThreadingHTTPServer` on `host_port` (0.0.0.0), Bearer `host_key`, `/api/ping`, `/api/transcribe` (int16 PCM, `X-Pass: preview` for live preview), `/api/rewrite`; one transcription at a time (`_model_lock`); `DeviceStats` → `%APPDATA%\VoiceTyper\server_devices.json` (active = seen < 10 min). Client: `Engine._remote_transcribe` / `rewrite()` try the host first and fall back to the local model on `RemoteError` (event `remote_down`). Connection code `VT1-` + base64 JSON {a: ip:port, k: key}. Tests bind 127.0.0.1 (no firewall prompt). Page: `gui/pages/remote_page.py`
- `updater.py` + `gui/updates.py` — automatic updates. Manifest `latest.json` on the latest release of the PUBLIC repo `hugocodings-design/Voice-Typer-Releases` (installers only; source stays private). `validate()` only accepts download URLs under that repo's releases; `download()` checks SHA-256; `install()` runs the setup detached with `/VERYSILENT /CLOSEAPPLICATIONS /UPDATE=1` and the app quits; the .iss `[Run]` entry with `Check: IsUpdate` restarts it with `--updated` (tray notice + `cleanup()`). Only frozen builds install. Release = bump `__version__`, `installeruild.ps1`, `installer\publish.ps1 -Notes …` (uses `gh`). Commits in the public repo use the GitHub noreply email
- `streaming.py` — live typing (`config.live_typing`, Réglages): `_live_loop` previews the last `WINDOW_S`=20 s every 0.6 s GPU / 1.5 s CPU / 1 s remote. `LiveTyper.update()` lines each pass up with the last 3 (or 2) typed words (case/punctuation-insensitive), types words two passes agree on; last word held back unless the pass is unchanged (= pause). Nothing typed until something was typed from the start (`from_start`). At release `finish(final)` erases from the first word that really differs (early comma/case changes are left as typed) and types the rest. Skipped while hotkey modifiers are held; off for AI presets; Esc erases what was typed. Guarded by `Engine._type_lock`
- `commands.py` — voice commands applied after dictionary replacements (`config.voice_commands`); `reference()` feeds the Help page
- Esc cancels a recording (`keyboard.on_press_key("esc", suppress=True)` armed only while recording)
- Live preview (`config.live_preview`): `recorder.snapshot()` → `transcriber.preview()` (greedy, no VAD) every 0.6 s GPU / 1.5 s CPU → overlay caption
- `rewrite_hotkey` copies the selection (sentinel + Ctrl+C), rewrites it with `rewrite_preset`, pastes; `app_presets` map an exe (`winapp.foreground_exe()`) to a preset for the main hotkey
- Look: bright green + gray. `voice_typer/theme/` = Sun Valley ttk theme (sv-ttk, MIT) recoloured by `tools/make_theme.py` (sprite sheets hue-shifted, Tcl colours edited); `ui_theme.PALETTES` holds the matching tk colours. Never use `tkinter.messagebox`/`simpledialog`: `gui/dialogs.py` gives themed pop-ups with the same API (`from voice_typer.gui import dialogs as messagebox`)
- Settings migrations live in `Config.load()` (`settings_version`)
- Tests: `python -m pytest` (+ `python -m pyflakes voice_typer tests`); CI on GitHub Actions installs from `requirements.lock` with `--require-hashes`
- Installer: `installer/build.ps1` → PyInstaller onedir (`voice_typer.spec`) → `Voice Typer.exe --selftest` → Inno Setup (`VoiceTyper.iss`, per-user, no admin). In the frozen app `gpu.py` looks in `sys._MEIPASS/nvidia/*/bin` and `autostart.py` registers the exe itself. The mutex `VoiceTyper.SingleInstance` is also the installer's `AppMutex`

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
- Bump `voice_typer/__init__.py` `__version__` before building a release installer.
