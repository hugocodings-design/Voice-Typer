"""Dictation engine: hotkey → recorder → transcriber → output.

The engine never touches the UI directly: it reports what happens through an event queue
that the window polls (tkinter must only be used from the main thread).
"""

import queue
import threading
import time

from voice_typer.config import Config
from voice_typer.hotkey import PushToTalk
from voice_typer.output import send_text
from voice_typer.recorder import Recorder
from voice_typer.transcriber import Transcriber

MIN_SECONDS = 0.3  # ignore accidental taps


class Engine:
    def __init__(self, config: Config):
        self.config = config
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.transcriber: Transcriber | None = None
        self.loading_source: str | None = None
        self.recorder = Recorder(config.sample_rate)
        self.hotkey = PushToTalk(config.hotkey, self._on_press, self._on_release)

    # ---- events -------------------------------------------------------------------------
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
    def _on_press(self) -> None:
        if self.transcriber is None:
            self._emit("status", "No model loaded yet — please wait")
            return
        self.recorder.start()
        self._emit("recording")

    def _on_release(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        if audio.size < MIN_SECONDS * self.config.sample_rate:
            self._emit("idle", "Too short, ignored")
            return
        threading.Thread(target=self._transcribe_and_send, args=(audio,), daemon=True).start()

    def _transcribe_and_send(self, audio) -> None:
        transcriber = self.transcriber
        if transcriber is None:
            return
        self._emit("transcribing")
        try:
            started = time.perf_counter()
            text = transcriber.transcribe(audio, self.config.language)
            elapsed = time.perf_counter() - started
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


def main() -> None:
    from voice_typer.gui import Window

    config = Config.load()
    engine = Engine(config)
    Window(engine).run()
