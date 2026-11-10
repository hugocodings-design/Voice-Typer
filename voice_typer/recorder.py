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

    def _callback(self, indata, frames, time, status):  # noqa: ARG002
        with self._lock:
            self._chunks.append(indata[:, 0].copy())

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
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)
