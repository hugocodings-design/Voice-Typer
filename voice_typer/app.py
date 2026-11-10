"""Wire hotkey → recorder → transcriber → output."""

import threading
import time

from voice_typer.config import Config
from voice_typer.hotkey import PushToTalk
from voice_typer.output import send_text
from voice_typer.recorder import Recorder
from voice_typer.transcriber import Transcriber

MIN_SECONDS = 0.3  # ignore accidental taps


class App:
    def __init__(self, config: Config):
        self.config = config
        print(f"Loading Whisper model '{config.model}' on {config.device} ({config.compute_type})…")
        self.transcriber = Transcriber(config)
        self.recorder = Recorder(config.sample_rate)
        self.hotkey = PushToTalk(config.hotkey, self._on_press, self._on_release)

    def _on_press(self) -> None:
        print("● Recording…")
        self.recorder.start()

    def _on_release(self) -> None:
        audio = self.recorder.stop()
        if audio.size < MIN_SECONDS * self.config.sample_rate:
            print("  (too short, ignored)")
            return
        threading.Thread(target=self._transcribe_and_send, args=(audio,), daemon=True).start()

    def _transcribe_and_send(self, audio) -> None:
        print("… Transcribing")
        started = time.perf_counter()
        text = self.transcriber.transcribe(audio)
        elapsed = time.perf_counter() - started
        print(f"✓ ({elapsed:.1f}s) {text!r}")
        send_text(text, self.config.output)

    def run(self) -> None:
        self.hotkey.start()
        print(f"Ready. Hold {self.config.hotkey} to dictate. Ctrl+C to quit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.hotkey.stop()


def main() -> None:
    App(Config()).run()
