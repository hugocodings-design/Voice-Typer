"""Dictation engine: hotkey → recorder → transcriber → (optional AI rewrite) → output.

The engine never touches the UI directly: it reports what happens through an event queue
that the window polls (tkinter must only be used from the main thread).
"""

import os
import queue
import sys
import threading
import time
import traceback

from voice_typer import cleanup, commands, dictionary, home, models, numerals, speed
from voice_typer.config import Config
from voice_typer.engine_home import HomeMixin
from voice_typer.engine_hotkeys import HotkeysMixin
from voice_typer.engine_writer import WriterMixin
from voice_typer.hotkey import Hotkey
from voice_typer.output import beep, send_text
from voice_typer.recorder import Recorder
from voice_typer.transcriber import Transcriber
from voice_typer.undo import UndoTracker

MIN_SECONDS = 0.3     # ignore accidental taps
MAX_SECONDS = 300     # safety stop in toggle mode
AUTO_HOLD_S = 0.4     # "auto" mode: held at least this long = push-to-talk, shorter tap = toggle


class Engine(WriterMixin, HotkeysMixin, HomeMixin):
    def __init__(self, config: Config):
        self.config = config
        config.ensure_presets()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.transcriber: Transcriber | None = None
        self.loading_source: str | None = None
        self.recorder = Recorder(config.sample_rate)
        self.hotkey = Hotkey(config.hotkey, lambda: self._on_down(None), lambda: self._on_up(None))
        self.lang_hotkey: Hotkey | None = None
        if config.language_hotkey:
            self.lang_hotkey = Hotkey(config.language_hotkey, self.cycle_language, lambda: None)
        self.last_text = ""                # last transcription sent (re-typed by paste_last_hotkey)
        self.paste_hotkey: Hotkey | None = None
        if config.paste_last_hotkey:
            try:
                self.paste_hotkey = Hotkey(config.paste_last_hotkey, self.paste_last, lambda: None)
            except Exception:  # noqa: BLE001
                self.paste_hotkey = None
        # « Annuler la dernière dictée » (shortcut + voice command « efface ça »)
        self.undo = UndoTracker(self._hotkey_scan_codes)
        self.undo_hotkey: Hotkey | None = None
        if config.undo_hotkey:
            try:
                self.undo_hotkey = Hotkey(config.undo_hotkey, self.undo_last, lambda: None)
            except Exception:  # noqa: BLE001
                self.undo_hotkey = None
        self._target_exe = ""              # application focused when the dictation started
        self._mic_missing = False          # chosen microphone was absent at the last dictation
        self.rewrite_hotkey: Hotkey | None = None
        if config.rewrite_hotkey:
            try:
                self.rewrite_hotkey = Hotkey(config.rewrite_hotkey, self.rewrite_selection, lambda: None)
            except Exception:  # noqa: BLE001
                self.rewrite_hotkey = None
        # AI writing presets: one global shortcut per preset (dictate, then rewrite)
        self.preset_hotkeys: dict[str, Hotkey] = {}
        self._hotkeys_running = False
        self._build_preset_hotkeys()
        self.writer = None                 # voice_typer.writer.Writer, loaded on demand
        self.writer_loading = False
        self._writer_lock = threading.Lock()
        self._active_preset: str | None = None
        self._record_started = 0.0
        self.busy = False                  # transcribing / rewriting (the floating mic button shows it)
        self._type_lock = threading.Lock()
        self._home_init()

    def _emit(self, kind: str, payload: object = None) -> None:
        self.events.put((kind, payload))

    # ---- model --------------------------------------------------------------------------
    def reload_model(self) -> None:
        """Reload the current model (e.g. after switching between GPU and CPU)."""
        source = self.transcriber.source if self.transcriber else self.config.model
        self.load_model(source)

    def load_model(self, source: str, device: str | None = None) -> None:
        """Download (if needed) and load a model in the background.

        The current model keeps working until the new one is ready, and stays if loading fails.
        """
        if self.loading_source is not None:
            return
        self.loading_source = source
        self._emit("model_loading", source)

        def work():
            try:
                started = time.perf_counter()
                path = models.resolve(source)  # downloads on first use
                where = device or self.model_device() or self.config.device
                new = models.retry_while_locked(lambda: Transcriber(
                    source, path, where,
                    self.config.compute_type, self.config.gpu_compute_type,
                    cpu_threads=speed.cpu_threads(self.config.all_cores)))
                self.transcriber = new
                self.config.model = source
                self.config.save()
                self._emit("model_loaded", (source, time.perf_counter() - started))
                if new.gpu_error:
                    self._emit("gpu_fallback", new.gpu_error)
            except Exception as exc:  # noqa: BLE001
                self._emit("model_error", (source, str(exc)))
            finally:
                self.loading_source = None

        threading.Thread(target=work, daemon=True).start()

    def _on_down(self, preset_id: str | None) -> None:
        self._press_started = None
        if self.config.mode in ("toggle", "auto") and self.recorder.is_recording:
            self._finish_recording()
            return
        if self.recorder.is_recording:
            return
        self._down_key = preset_id  # which key's release ends a hold (None = main dictation key)
        self._press_started = time.monotonic()  # "auto": a long press ends at release, a tap doesn't
        try:
            from voice_typer.winapp import foreground_exe

            self._target_exe = foreground_exe()
        except Exception:  # noqa: BLE001 — never block dictation over this
            self._target_exe = ""
        if preset_id is None:
            try:
                preset_id = self.preset_for_app(self._target_exe)
            except Exception:  # noqa: BLE001
                preset_id = None
        self._active_preset = preset_id
        self._start_recording()

    def _on_up(self, preset_id: str | None) -> None:
        if preset_id != getattr(self, "_down_key", None):
            return
        started, self._press_started = getattr(self, "_press_started", None), None
        if self.config.mode == "hold":
            self._finish_recording()
        elif (self.config.mode == "auto" and started is not None and self.recorder.is_recording
              and time.monotonic() - started >= AUTO_HOLD_S):
            self._finish_recording()  # held down while speaking → push-to-talk

    def _start_recording(self) -> None:
        if self.transcriber is None:
            self._emit("status", "no_model")
            return
        if self.recorder.is_recording:
            return
        self.recorder.device_name = self.config.input_device
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001 — no microphone, device busy…
            self._emit("idle", f"Micro : {exc}")
            return
        self._check_microphone()
        self.undo.suspend()   # our own typing / Ctrl+V doesn't invalidate the last dictation
        if self.config.sounds:
            beep(True)
        self._record_started = time.monotonic()
        self._arm_escape()
        try:
            self.wake_home(self._active_preset)   # the home PC loads its models while we listen
        except Exception:  # noqa: BLE001 — never block dictation over this
            pass
        self._emit("recording", self.preset(self._active_preset))
        if self.config.mode in ("toggle", "auto"):
            threading.Thread(target=self._safety_stop, args=(self._record_started,), daemon=True).start()

    def _check_microphone(self) -> None:
        """Chosen microphone unplugged → the Windows default is used, and it switches back by
        itself at the first dictation after it is reconnected. Tell the user both times."""
        missing = self.recorder.using_fallback
        if missing != self._mic_missing:
            self._mic_missing = missing
            self._emit("mic_fallback" if missing else "mic_back", self.config.input_device)

    # ---- Esc cancels the dictation in progress (swallowed so it doesn't also close a dialog)
    def _arm_escape(self) -> None:
        import keyboard

        self._disarm_escape()
        try:
            self._esc_hook = keyboard.on_press_key(
                "esc", lambda _e: threading.Thread(target=self.cancel_recording, daemon=True).start(),
                suppress=True)
        except Exception:  # noqa: BLE001
            self._esc_hook = None

    def _disarm_escape(self) -> None:
        import keyboard

        hook = getattr(self, "_esc_hook", None)
        self._esc_hook = None
        if hook is not None:
            try:
                keyboard.unhook(hook)
            except (KeyError, ValueError):
                pass

    def cancel_recording(self) -> None:
        self._disarm_escape()
        if not self.recorder.is_recording:
            return
        self.recorder.stop()
        self.undo.resume()
        if self.config.sounds:
            beep(False)
            beep(False)
        self._emit("cancelled")

    @staticmethod
    def _erase(n: int) -> None:
        import keyboard

        for _ in range(n):
            keyboard.send("backspace")
            time.sleep(0.002)

    def _safety_stop(self, started: float) -> None:
        time.sleep(MAX_SECONDS)
        if self.recorder.is_recording and self._record_started == started:
            self._finish_recording()

    def _finish_recording(self) -> None:
        self._disarm_escape()
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        if self.config.sounds:
            beep(False)
        if audio.size < MIN_SECONDS * self.config.sample_rate:
            self.undo.resume()
            self._emit("idle", "too_short")
            return
        threading.Thread(target=self._transcribe_and_send, args=(audio, self._active_preset),
                         daemon=True).start()

    def _wait_modifiers_released(self, timeout: float = 3.0) -> None:
        # Pasting with Ctrl/Alt still physically held would send e.g. Ctrl+Alt+V instead of Ctrl+V.
        deadline = time.monotonic() + timeout
        keys = self._all_hotkeys()
        while any(k.modifiers_held() for k in keys) and time.monotonic() < deadline:
            time.sleep(0.03)

    def _transcribe_and_send(self, audio, preset_id: str | None = None) -> None:
        self.busy = True
        try:
            self._transcribe_and_send_inner(audio, preset_id)
        finally:
            self.busy = False
            self.undo.resume()

    # ---- « PC à la maison » (engine_home.py): home PC first, local models as fallback
    def _transcribe_audio(self, transcriber, audio, language, hotwords, timings: dict) -> str:
        client = self.home_client()
        if client is not None:
            try:
                text = client.transcribe(audio, self.config.sample_rate, language, hotwords, self.config.speed_mode,
                                         self.config.model)
                timings["home"] = 1.0
                seconds = client.last_answer.get("seconds")
                if isinstance(seconds, (int, float)):
                    timings["home_compute"] = float(seconds)   # on the home PC; the rest is the network
                self._home_result(True)
                return text
            except home.HomeError as exc:
                self._home_result(False, str(exc))
        return transcriber.transcribe(audio, language, hotwords, mode=self.config.speed_mode)

    def _transcribe_and_send_inner(self, audio, preset_id: str | None = None) -> None:
        transcriber = self.transcriber
        if transcriber is None:
            return
        self._emit("transcribing")
        try:
            started = time.perf_counter()
            # where the time goes, shown after the dictation (speed.format_timings)
            timings = {"audio": audio.size / float(self.config.sample_rate)}
            language = self.config.language
            vocabulary, replacements = dictionary.for_app(self.config.vocabulary, self.config.replacements,
                                                          self.config.app_dictionaries, self._target_exe)
            hotwords = dictionary.hotwords(vocabulary)
            text = self._transcribe_audio(transcriber, audio, language, hotwords, timings)
            timings["transcribe"] = time.perf_counter() - started
            text = cleanup.strip_hallucinations(text)
            if self.config.remove_fillers:
                text = cleanup.remove_fillers(text, language)
            if self.config.numbers_as_digits:
                text = numerals.to_digits(text, language)
            text = dictionary.apply_replacements(text, replacements)
            if self.config.voice_commands and commands.is_undo(text, language):
                self._voice_undo()
                return
            if self.config.voice_commands:
                text = commands.apply(text, language)
            raw = text
            preset = self.preset(preset_id)
            if preset and text.strip():
                self._emit("rewriting", preset)
                try:
                    self.last_rewrite_timings = {}
                    t_rewrite = time.perf_counter()
                    text = self.rewrite(text, preset)
                    text = dictionary.apply_replacements(text, replacements)
                    timings.update(self.last_rewrite_timings or {"rewrite": time.perf_counter() - t_rewrite})
                except Exception as exc:  # noqa: BLE001 — never lose the dictation
                    traceback.print_exc()
                    self._emit("writer_error", f"{type(exc).__name__}: {exc}")
                    text = raw
            elapsed = time.perf_counter() - started
            self._wait_modifiers_released()
            if text:
                self.last_text = text
            trailing = self.config.trailing_space and preset is None
            with self._type_lock:
                send_text(text, self.config.output, trailing, self.config.keep_in_clipboard)
            typed = text + (" " if text and trailing else "")
            if typed:
                self.undo.record(typed)
            timings["paste"] = max(0.0, time.perf_counter() - started - elapsed)
            self._emit("transcript", (text, elapsed, language, preset["name"] if preset else None, raw, timings))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._emit("idle", f"Error: {exc}")

    def _voice_undo(self) -> None:
        """« efface ça » said alone: remove the previous dictation."""
        self._wait_modifiers_released()
        self._undo_now()
        self._emit("idle", None)

    # ---- lifecycle ----------------------------------------------------------------------
    def start(self) -> None:
        self.resume_hotkey()
        self.start_home_watch()   # first: Home Connections on this PC keeps the graphics card for itself
        self.load_model(self.config.model)
        # not with a home PC: it writes the emails; the local copy is loaded only if it stops answering
        if self.config.writer_preload and self.preset_hotkeys and not self._local_home and not self.config.home_enabled:
            from voice_typer import writer

            if writer.is_downloaded(self.config.writing_model):
                self.load_writer()

    def cleanup_firewall_later(self) -> None:
        """Power sharing is gone (0.9.3): remove the firewall rules it may have needed."""
        def work():
            from voice_typer import legacy

            left = legacy.cleanup_firewall()
            if left:
                self._emit("firewall_left", left)

        threading.Thread(target=work, daemon=True).start()

    def stop(self) -> None:
        self.stop_home_watch()
        self.pause_hotkey()
        if self.recorder.is_recording:
            self.recorder.stop()

MUTEX_NAME = "VoiceTyper.SingleInstance"


def _already_running(wait: float = 0.0) -> bool:
    """Single instance: a second copy would type everything twice.

    `wait` (seconds): after a restart, give the previous copy time to finish closing."""
    import ctypes

    k32 = ctypes.windll.kernel32
    deadline = time.monotonic() + wait
    while True:
        handle = k32.CreateMutexW(None, False, MUTEX_NAME)
        if k32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
            return False  # keep the handle open for the whole life of the app
        if handle:
            k32.CloseHandle(handle)  # don't keep the other copy's mutex alive
        if time.monotonic() >= deadline:
            return True
        time.sleep(0.25)


def _take_over(config: Config) -> bool:
    """Voice Typer is already running. Bring its window to the front and stop here (False).

    If that copy does not answer (frozen, or stuck in the background with no window), offer to close it
    and start this one instead: True = this launch continues with the single-instance mutex.
    """
    from voice_typer import instance

    if "--restart" not in sys.argv and instance.ask_existing_to_show():
        return False  # its window is now in front: nothing more to do, no message

    import tkinter as tk

    from voice_typer import ui_theme
    from voice_typer.gui import dialogs
    from voice_typer.i18n import tr

    root = tk.Tk()
    root.withdraw()
    mode, pal = ui_theme.apply(root, config.theme)
    dialogs.configure(mode, pal, ui_theme.Fonts(root), config.ui_language)
    lang = config.ui_language
    try:
        if not dialogs.askyesno("Voice Typer", tr(lang, "instance_frozen"), parent=root):
            return False
        instance.close_frozen_copy()
        if not _already_running(wait=8.0):
            return True
        dialogs.showinfo("Voice Typer", tr(lang, "instance_still_running"), parent=root)
        return False
    finally:
        root.destroy()


def restart_command() -> list[str]:
    """Command line that starts this app again (packaged exe or `python -m voice_typer`)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--restart"]
    return [sys.executable, "-m", "voice_typer", "--restart"]


def selftest() -> int:
    """`--selftest`: checks a packaged build has everything it needs (run by installer/build.ps1)."""
    try:
        import importlib

        import numpy as np

        for name in ("keyboard", "pystray", "sounddevice", "sv_ttk", "tokenizers",
                     "voice_typer.gui", "voice_typer.transcriber", "voice_typer.writer", "voice_typer.transfer",
                     "voice_typer.instance", "voice_typer.mic_button", "voice_typer.cleanup", "voice_typer.report", "voice_typer.portable"):
            importlib.import_module(name)
        from faster_whisper.vad import get_speech_timestamps

        get_speech_timestamps(np.zeros(16000, dtype=np.float32))  # VAD model (onnxruntime)
        # update signatures need `cryptography`; downloads (models, updates) need `ssl` in the build
        import base64
        import ssl

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        from voice_typer import legacy, update_key

        Ed25519PublicKey.from_public_bytes(base64.b64decode(update_key.UPDATE_PUBLIC_KEY))
        ssl.create_default_context()
        assert callable(legacy.remove_power_sharing)
        from voice_typer import gpu

        print(f"SELFTEST OK cuda_devices={int(gpu.cuda_available())}", flush=True)
        return 0
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("SELFTEST FAILED", flush=True)
        return 1


def main() -> None:
    from voice_typer.portable import use_private_temp

    use_private_temp()  # already done by run.pyw; also covers `python -m voice_typer`
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    config = Config.load()
    if _already_running(wait=15.0 if "--restart" in sys.argv else 0.0) and not _take_over(config):
        return

    from voice_typer import legacy
    from voice_typer.gui import Window

    cleaned = legacy.remove_power_sharing()  # once, after the update from a version with power sharing
    engine = Engine(config)
    if not cleaned["done_before"]:
        engine.cleanup_firewall_later()
    updated = "--updated" in sys.argv
    Window(engine).run(start_hidden="--minimized" in sys.argv or updated, updated=updated)
    # The window is closed: end the process for real. Library threads (keyboard hooks, tray, audio) could
    # otherwise keep it alive with no window, and every launch would then say "already open".
    sys.stdout.flush() if sys.stdout else None
    sys.stderr.flush() if sys.stderr else None
    os._exit(0)
