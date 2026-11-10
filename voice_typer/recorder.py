"""Microphone capture into an in-memory float32 buffer."""

import threading

import numpy as np
import sounddevice as sd


class Recorder:
    def __init__(self, sample_rate: int = 16_000):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self.level = 0.0  # last input loudness (RMS, 0..~1), for the on-screen meter

    def _callback(self, indata, frames, time, status):  # noqa: ARG002
        mono = indata[:, 0]
        self.level = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
        with self._lock:
            self._chunks.append(mono.copy())

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32", callback=self._callback
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return the captured audio (mono float32, sample_rate Hz)."""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self.level = 0.0
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)
