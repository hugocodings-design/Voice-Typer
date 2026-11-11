"""Microphone capture into an in-memory float32 buffer."""

import threading

import numpy as np
import sounddevice as sd

_DIRECTSOUND = "Windows DirectSound"


def list_microphones() -> list[str]:
    """Input devices with their full names (DirectSound; MME truncates names to 31 chars)."""
    try:
        apis = sd.query_hostapis()
        ds = next((i for i, a in enumerate(apis) if a["name"] == _DIRECTSOUND), None)
        names = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and (ds is None or d["hostapi"] == ds):
                if d["name"] not in names and "Pilote de capture" not in d["name"] \
                        and "Primary Sound Capture" not in d["name"]:
                    names.append(d["name"])
        return names
    except Exception:  # noqa: BLE001
        return []


def _device_index(name: str | None) -> int | None:
    if not name:
        return None
    try:
        apis = sd.query_hostapis()
        ds = next((i for i, a in enumerate(apis) if a["name"] == _DIRECTSOUND), None)
        for i, d in enumerate(sd.query_devices()):
            if d["name"] == name and d["max_input_channels"] > 0 and (ds is None or d["hostapi"] == ds):
                return i
    except Exception:  # noqa: BLE001
        pass
    return None  # unplugged → Windows default


class Recorder:
    def __init__(self, sample_rate: int = 16_000):
        self.sample_rate = sample_rate
        self.device_name: str | None = None
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
        device = _device_index(self.device_name)
        try:
            self._stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                                          callback=self._callback, device=device)
        except Exception:  # noqa: BLE001 — chosen mic failed: use the Windows default
            self._stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                                          callback=self._callback)
        self._stream.start()

    def snapshot(self, max_seconds: float = 30.0) -> np.ndarray:
        """Audio captured so far (last max_seconds), without stopping — for the live preview."""
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks)
        return audio[-int(max_seconds * self.sample_rate):]

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
