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
- `voice_typer/app.py` — `Engine`: hotkey down → record; up → transcribe in a worker thread, output text. Reports to the UI only via `engine.events` (a queue). Split into mixins: `engine_writer.py` (AI presets / writer), `engine_hotkeys.py` (secondary shortcuts, undo, rewrite selection, per-app presets); recording/transcription/lifecycle stay in `app.py`. `config.mode`: "hold" (release ends), "toggle" (2nd press ends), "auto" (2nd press ends; a release ends it only if held ≥ `AUTO_HOLD_S`=0.4 s). Shortcut with no model → `status/no_model` event → Home line + overlay flash ("loading" vs "pick one")
- `undo.py` — `UndoTracker`: `record(typed)` after each dictation; `take()` gives the text back only if same foreground window, no key typed (our shortcuts' scan codes, modifiers, Esc ignored), no mouse click (WH_MOUSE_LL hook) and < 10 min. `suspend()/resume()` around our own typing (recording → delivery). Voice command `commands.is_undo()` = « efface ça » said ALONE. Events `undone` / `undo_refused` (reason)
- Per-app dictionary: `config.app_dictionaries` [{app, vocabulary, replacements}], merged by `dictionary.for_app()` with `Engine._target_exe` (focused exe at key down); an app replacement overrides the general one with the same `from`
- Microphone: `config.input_device` is kept while unplugged; `recorder.refresh_devices()` re-scans PortAudio (`sd._terminate/_initialize`, never while a stream is open) when it is missing; `Recorder.using_fallback` → events `mic_fallback` / `mic_back`
- Clipboard: `output.send_text` saves ALL formats (`clipboard.snapshot/restore`), offers the text with delayed rendering (`offer_delayed`: hidden message-only window answers WM_RENDERFORMAT, so we know when the app pasted), restores after the read (+0.3 s) or after 2.5 s; not restored if the user copied something else meanwhile. Clipboard sync tools (Android emulator, Phone Link, RDP, clipboard managers) read every new clipboard within ms: `_DelayedText.reader_hwnd` records who asked; if it is not the focused app's process, `wait_until_pasted` polls `GetOpenClipboardWindow` until the focused process opens the clipboard
- **No network server, ever** (IT requirement, 0.9.3): power sharing (`remote.py`, port 8765) was removed; the only network access is model downloads (Hugging Face) and update checks (Voice-Typer-Releases). `tests/test_no_network_server.py` fails on any `listen`/`bind`/HTTP server. `legacy.py` runs once at startup (marker `%APPDATA%\VoiceTyper\power_sharing_removed`): deletes old sharing keys from settings.json and `host_certificate*.pem` / `server_devices.json`; then `Engine.cleanup_firewall_later()` looks for firewall rules naming the frozen exe (never python.exe) and, if they can't be removed without admin, the window asks (only when shown) and runs `Remove-NetFirewallRule` elevated
- `transfer.py` — settings export/import (Réglages → Transférer vers un autre PC). Allowlist `PORTABLE` (user's work and taste only: never mic, update state, history, local model folders); `read_export` validates types, `apply_settings` merges `custom_models` (keeps this PC's local folders). Import saves then `Window._restart()` → new process with `--restart`, which waits up to 15 s for the single-instance mutex (`app.MUTEX_NAME`)
- `voice_typer/gui/` — tkinter window polling `engine.events`; never call tkinter from worker threads. `window.py` = `Window` built from page mixins (`pages/*.py`), `wizard.py` (first-run assistant, `config.first_run_done`), `shortcuts.py` (recorder + conflict check `_taken_hotkeys`)
- `voice_typer/models.py` — model catalog (speed/accuracy), language list, download/import helpers
- `voice_typer/config.py` — settings dataclass saved to `%APPDATA%\VoiceTyper\settings.json`
- `voice_typer/hotkey.py` — suppressing low-level hook: the trigger key is swallowed while the combo is held; a mask key (VK 0xE8) stops Alt/Win from opening menus. Callbacks run on a worker thread (hooks must return fast)
- `voice_typer/overlay.py` — click-through, non-activating pill; shown/hidden via opacity (re-showing a window can steal focus). 360 px: label on the left measured and cut with « … » (`fit`) so it never runs under the wave; the wave has its own rounded zone on the right (20 round-capped bars, scrolling history, fast attack / slow decay, taller in the middle). With a preset the label is "Courriel · FR"
- `speed.py` — Réglages → Vitesse: `speed_mode` "auto" (fast on CPU, accurate on GPU) | "fast" (beam 1, no timestamps, no previous-text conditioning) | "accurate" (beam 5), read at each dictation by `Transcriber.transcribe(mode=)`; `all_cores` → `cpu_threads()` ≈ physical cores (CTranslate2 defaults to 4) for Whisper AND the writer (`intra_threads`), applied by reloading the models. Timings (audio, transcribe, rewrite, subject, paste) travel as the 6th item of the `transcript` event, shown on Home (`format_timings`) and saved in history
- `voice_typer/tray.py`, `autostart.py`, `i18n.py` — tray icon, HKCU Run autostart, FR/EN strings (every UI text goes through `tr()`)
- `run.pyw` — under pythonw `sys.stdout/stderr` are None: it redirects them to `%APPDATA%\VoiceTyper\voice_typer.log` (tracebacks land there) and disables HF progress bars, which otherwise crash downloads/loads (`'NoneType' object has no attribute 'write'`). Test console-less behaviour with pythonw, not python
- `run.pyw` — console-less entry used by `Start Voice Typer.bat` and autostart (`--minimized` starts in the tray)
- Single instance enforced with a named mutex (two instances would type everything twice). `instance.py`: a second
  launch sets the named event `VoiceTyper.ShowWindow` (after `AllowSetForegroundWindow`); the running copy
  (`wait_for_launches`, started in `Window.run`) shows its window via `call_soon` and sets `…Ack` FROM THE TK THREAD,
  so a frozen copy doesn't answer → `app._take_over` asks to close it (`close_frozen_copy`: PID from
  `%APPDATA%\VoiceTyper\instance.pid`, only if the image is our exe) and continues. Events only, no socket (the
  no-network test also forbids the text `.listen(`). `main()` ends with `os._exit(0)` after the window closes
  (library threads used to keep a windowless process alive → "already open" forever). `config.close_action`
  "ask" (first ✕ asks, then remembered) | "tray" | "quit" (Réglages → Démarrage)
- `voice_typer/gpu.py` — adds `site-packages/nvidia/*/bin` (cuBLAS 12 from `nvidia-cublas-cu12`) to the DLL search path; must run before CTranslate2 uses CUDA (done at `transcriber.py` import). `Transcriber` tries CUDA float16 with a warm-up, falls back to CPU int8 and reports `gpu_error`
- `_build()` rebuilds every page (theme/UI-language change) but keeps Toplevels (overlay caption, assistant). `ui_theme.py` = sv-ttk + palettes + Segoe Fluent icon glyphs
- `voice_typer/dictionary.py` — vocabulary → faster-whisper `hotwords`; replacements = case-insensitive whole-phrase regex after transcription
- `voice_typer/languages.py` — French and English only (`SUPPORTED`; the user's models are multilingual or FR/EN specialists, so no Languages page). `config.language` is None (auto) / fr / en, forced on load; `config.language_hotkey` toggles FR ↔ EN (set on Home). The full list only names old history entries
- History lives in `%APPDATA%\VoiceTyper\history.json` (separate from settings)
- Microphones are listed/opened through the DirectSound host API (MME truncates names)
- Dev machine: RTX 2080 Super 8 GB — GPU makes large models ~20× faster than CPU
- `voice_typer/recorder.py`, `transcriber.py`, `output.py`, `hotkey.py` — one concern each
- `voice_typer/writer.py` — AI writing presets: embedded LLM (CTranslate2 `Generator` + `tokenizers`, Qwen 2.5 Instruct int8, manual ChatML prompt with one few-shot example). **No Ollama / server software** — the user installs this on a work PC too. `Engine` keeps one `Hotkey` per preset (`config.presets`: id/name/hotkey/instructions, `None` = defaults), records with `_active_preset`, then `rewrite()`; on failure the raw text is typed. `writer_preload` keeps the LLM in memory. **Signature and subject are NOT left to the model** (`compose.py`): sentences about them are stripped from the instructions (`model_instructions`, keeps "Termine par « Merci, »" from "… suivie de cette signature : {signature}"); per-preset switches `add_signature` / `subject` (missing = guessed from the instructions by `preset_flags`, negation checked just before each mention); `finish_signature` appends `config.signature` (after an empty line if `config.signature_blank_line`) unless the text already ends with one (configured first line, or a short name after the closing formula, or "Merci, Hugo"); the subject is a 2nd tiny request (`SUBJECT_SYSTEM`) put on line 1 ("Objet : …" / "Subject: …"). Leaked notes like "(aucune signature)" are removed. Language: `compose.detect_language` (stop words) on the dictation picks SYSTEM_FR/SYSTEM_EN + matching few-shot example (EN adds `EN_RULES_NOTE`: French instructions still apply), one retry if an English dictation came back French, `config.signature_en` ("" = same signature), subject label by language. `drop_copied_example` removes sentences copied from the few-shot example that were not dictated. Preset editor: tall scrollable instructions + "Ouvrir en grand" window; `common.ScrollFrame` leaves the wheel to text boxes / lists that can scroll
- `updater.py` + `gui/updates.py` — automatic updates. Manifest `latest.json` on the latest release of the PUBLIC repo `hugocodings-design/Voice-Typer-Releases` (installers only; source stays private). `validate()` only accepts download URLs under that repo's releases; `download()` checks SHA-256; `install()` runs the setup detached with `/VERYSILENT /CLOSEAPPLICATIONS /UPDATE=1` and the app quits; the .iss `[Run]` entry with `Check: IsUpdate` restarts it with `--updated` (tray notice + `cleanup()`). Only frozen builds install. `latest.json` carries an ed25519 `signature` (`installer/sign.py`, private key `%USERPROFILE%\.voice-typer\update-signing-key.pem`, never in the repo; public key `update_key.py`); `validate()` refuses unsigned / badly signed manifests (0.8.x ignores the field). Release = bump `__version__`, `installer\build.ps1`, `installer\publish.ps1 -Notes …` (uses `gh`). Or from the cloud: bump `__version__` AND `installer/release-notes.json` (version, fr, en, required) on master → `.github/workflows/release.yml` (windows-latest: venv from requirements.lock, Inno Setup, build.ps1, publish.ps1 with secrets `VT_UPDATE_SIGNING_KEY` → `VT_SIGNING_DIR`, `RELEASES_TOKEN` → `GH_TOKEN`); does nothing without the secrets or if the version is already released. Commits in the public repo use the GitHub noreply email
- `streaming.py` — live typing (`config.live_typing`, Réglages): `_live_loop` previews the last `WINDOW_S`=20 s every 0.6 s GPU / 1.5 s CPU. `LiveTyper.update()` lines each pass up with the last 3 (or 2) typed words (case/punctuation-insensitive), types words two passes agree on; last word held back unless the pass is unchanged (= pause). Nothing typed until something was typed from the start (`from_start`). At release `finish(final)` erases from the first word that really differs (early comma/case changes are left as typed) and types the rest. Skipped while hotkey modifiers are held; off for AI presets; Esc erases what was typed. Guarded by `Engine._type_lock`
- `mic_button.py` — floating mic button (Voice Typer Mobile's bubble): WS_EX_NOACTIVATE + TOOLWINDOW (clickable,
  never focused), shown/hidden via alpha like the overlay. Click → `Engine.button_dictate()` (start/stop in any
  mode, `_down_key = BUTTON_KEY` so shortcut releases don't end it, safety stop also in hold mode); drag saves
  `config.mic_button_pos` (not exported); right-click → menu (presets, `set_app_preset`, language, paste_last,
  undo_last, hide), right-click while recording = cancel. The menu takes focus: the previous foreground window is
  restored (`SetForegroundWindow`) before the action. State is polled (`recorder.is_recording`, `Engine.busy`).
  `UndoTracker.ignore_click` = `MicButton.owns_click` so clicks on it/its menu don't invalidate undo
- `numerals.py` — `to_digits(text, language)`: numbers said in words → digits (FR incl. quatre-vingt/septante/
  « vingt et un », EN incl. "a hundred and five", years "nineteen eighty-four"); « virgule »/"point" decimals,
  « pour cent »/"percent" → %. Keeps "un/une/one", "mille", "zéro" alone, "neuf" = new, hyphenated words. Applied
  after fillers, before dictionary/commands, also to the live preview (`config.numbers_as_digits`, Réglages)
- `cleanup.py` — shared with mobile `Text.kt`: `strip_hallucinations` (always, right after Whisper) and
  `remove_fillers` (`config.remove_fillers`), both before dictionary replacements
- `portable.py` — never %TEMP% (company ASR rules): `use_private_temp()` (first thing in run.pyw and `main()`)
  sets TEMP/TMP/TMPDIR + `tempfile.tempdir` to `<app>\tmp` if `portable.txt` sits next to the exe (portable zip,
  e.g. C:\Dev\VoiceTyper), else `%LOCALAPPDATA%\VoiceTyper\tmp`; the update installer inherits it (Inno unpacks
  its helper in TMP). `installer/make_portable.py` (build.ps1) → `dist/VoiceTyper-portable-<v>.zip` (folder build
  at the zip root + portable.txt); `sign.py --portable` adds signed `portable_url/_sha256/_size`; publish.ps1
  uploads it. Portable updates: `updater.asset()` picks the zip, `unpack_portable` (path-traversal check, keeps the
  marker) into tmp, `install_portable` → cmd `ping`, `robocopy new → app /E`, `rd`, restart `--updated`
- `report.py` — « Signaler un problème » (Réglages + tray): `diagnostic.export` to Downloads, then classic Outlook
  `/c ipm.note /m "<addr>&subject=…&body=…" /a <zip>` (App Paths registry), else `mailto:` + Explorer `/select`.
  `SUPPORT_EMAIL` = the developer's address. `diagnostic.PRIVATE_FIELDS` also strips `app_dictionaries`
- Required updates: `latest.json` `"required": true` (signed; `sign.py --required`, `publish.ps1 -Required`);
  `updater.is_required`. The 6-h check always runs; with `auto_update` off or a skipped version only a required
  update is acted on; it hides Later/Skip and `_upd_install_when_idle` installs when not recording/busy (30 s retry)
- Code signing: `build.ps1` also supports Microsoft Trusted Signing (`%USERPROFILE%\.voice-typer\trusted-signing.json`
  metadata + `Azure.CodeSigning.Dlib.dll`), besides PFX / thumbprint
- `config.suggest_app_presets` — "Ajouter les suggestions" on the AI writing page (never overrides user rules)
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
