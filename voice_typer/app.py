"""Dictation engine: hotkey → recorder → transcriber → output.

The engine never touches the UI directly: it reports what happens through an event queue
that the window polls (tkinter must only be used from the main thread).
"""

import queue
import sys
import threading
import time

from voice_typer.config import Config
from voice_typer.hotkey import Hotkey
from voice_typer.output import send_text
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
        self._record_started = 0.0

    def _emit(self, kind: str, payload: object = None) -> None:
        self.events.put((kind, payload))

    # ---- model --------------------------------------------------------------------------
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
                new = Transcriber(source, self.config.device, self.config.compute_type)
                self.transcriber = new
                self.config.model = source
                self.config.save()
                self._emit("model_loaded", (source, time.perf_counter() - started))
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

    def pause_hotkey(self) -> None:
        self.hotkey.stop()

    def resume_hotkey(self) -> None:
        self.hotkey.start()

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
        self.recorder.start()
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
            text = transcriber.transcribe(audio, self.config.language)
            elapsed = time.perf_counter() - started
            self._wait_modifiers_released()
            send_text(text, self.config.output)
            self._emit("transcript", (text, elapsed))
        except Exception as exc:  # noqa: BLE001
            self._emit("idle", f"Error: {exc}")

    # ---- lifecycle ----------------------------------------------------------------------
    def start(self) -> None:
        self.hotkey.start()
        self.load_model(self.config.model)

    def stop(self) -> None:
        self.hotkey.stop()
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
