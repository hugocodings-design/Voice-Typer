"""Dictation engine: hotkey → recorder → transcriber → output.

The engine never touches the UI directly: it reports what happens through an event queue
that the window polls (tkinter must only be used from the main thread).
"""

import queue
import sys
import threading
import time

from voice_typer import dictionary, models
from voice_typer.config import Config
from voice_typer.hotkey import Hotkey
from voice_typer.output import beep, send_text
from voice_typer.recorder import Recorder
from voice_typer.transcriber import Transcriber

MIN_SECONDS = 0.3     # ignore accidental taps
MAX_SECONDS = 300     # safety stop in toggle mode


class Engine:
    def __init__(self, config: Config):
        self.config = config
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.transcriber: Transcriber | None = None
        self.loading_source: str | None = None
        self.recorder = Recorder(config.sample_rate)
        self.hotkey = Hotkey(config.hotkey, self._on_down, self._on_up)
        self.lang_hotkey: Hotkey | None = None
        if config.language_hotkey:
            self.lang_hotkey = Hotkey(config.language_hotkey, self.cycle_language, lambda: None)
        self._record_started = 0.0

    def _emit(self, kind: str, payload: object = None) -> None:
        self.events.put((kind, payload))

    # ---- model --------------------------------------------------------------------------
    def reload_model(self) -> None:
        """Reload the current model (e.g. after switching between GPU and CPU)."""
        source = self.transcriber.source if self.transcriber else self.config.model
        self.load_model(source)

    def load_model(self, source: str) -> None:
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
                new = Transcriber(source, path, self.config.device,
                                  self.config.compute_type, self.config.gpu_compute_type)
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

    # ---- hotkey -------------------------------------------------------------------------
    def set_hotkey(self, combo: str) -> None:
        self.hotkey.set_combo(combo)
        self.config.hotkey = self.hotkey.combo
        self.config.save()

    def set_language_hotkey(self, combo: str) -> None:
        if self.lang_hotkey:
            self.lang_hotkey.stop()
            self.lang_hotkey = None
        self.config.language_hotkey = combo
        if combo:
            self.lang_hotkey = Hotkey(combo, self.cycle_language, lambda: None)
            self.config.language_hotkey = self.lang_hotkey.combo
            self.lang_hotkey.start()
        self.config.save()

    def pause_hotkey(self) -> None:
        self.hotkey.stop()
        if self.lang_hotkey:
            self.lang_hotkey.stop()

    def resume_hotkey(self) -> None:
        self.hotkey.start()
        if self.lang_hotkey:
            self.lang_hotkey.start()

    # ---- language -----------------------------------------------------------------------
    def set_language(self, code: str | None) -> None:
        self.config.language = code
        self.config.save()
        self._emit("language_changed", code)

    def cycle_language(self) -> None:
        favs = [c for c in self.config.favorite_languages if c]
        if not favs:
            return
        cur = self.config.language
        nxt = favs[(favs.index(cur) + 1) % len(favs)] if cur in favs else favs[0]
        self.set_language(nxt)

    def _on_down(self) -> None:
        if self.config.mode == "toggle" and self.recorder.is_recording:
            self._finish_recording()
            return
        self._start_recording()

    def _on_up(self) -> None:
        if self.config.mode == "hold":
            self._finish_recording()

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
        if self.config.sounds:
            beep(True)
        self._record_started = time.monotonic()
        self._emit("recording")
        if self.config.mode == "toggle":
            threading.Thread(target=self._safety_stop, args=(self._record_started,), daemon=True).start()

    def _safety_stop(self, started: float) -> None:
        time.sleep(MAX_SECONDS)
        if self.recorder.is_recording and self._record_started == started:
            self._finish_recording()

    def _finish_recording(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        if self.config.sounds:
            beep(False)
        if audio.size < MIN_SECONDS * self.config.sample_rate:
            self._emit("idle", "too_short")
            return
        threading.Thread(target=self._transcribe_and_send, args=(audio,), daemon=True).start()

    def _wait_modifiers_released(self, timeout: float = 3.0) -> None:
        # Pasting with Ctrl/Alt still physically held would send e.g. Ctrl+Alt+V instead of Ctrl+V.
        deadline = time.monotonic() + timeout
        while self.hotkey.modifiers_held() and time.monotonic() < deadline:
            time.sleep(0.03)

    def _transcribe_and_send(self, audio) -> None:
        transcriber = self.transcriber
        if transcriber is None:
            return
        self._emit("transcribing")
        try:
            started = time.perf_counter()
            language = self.config.language
            text = transcriber.transcribe(audio, language, dictionary.hotwords(self.config.vocabulary))
            text = dictionary.apply_replacements(text, self.config.replacements)
            elapsed = time.perf_counter() - started
            self._wait_modifiers_released()
            send_text(text, self.config.output, self.config.trailing_space)
            self._emit("transcript", (text, elapsed, language))
        except Exception as exc:  # noqa: BLE001
            self._emit("idle", f"Error: {exc}")

    # ---- lifecycle ----------------------------------------------------------------------
    def start(self) -> None:
        self.resume_hotkey()
        self.load_model(self.config.model)

    def stop(self) -> None:
        self.pause_hotkey()
        if self.recorder.is_recording:
            self.recorder.stop()


def _already_running() -> bool:
    """Single instance: a second copy would type everything twice."""
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, "VoiceTyper.SingleInstance")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    config = Config.load()
    if _already_running():
        import tkinter as tk
        from tkinter import messagebox

        from voice_typer.i18n import tr

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Voice Typer", tr(config.ui_language, "already_running"))
        root.destroy()
        return

    from voice_typer.gui import Window

    engine = Engine(config)
    Window(engine).run(start_hidden="--minimized" in sys.argv)
