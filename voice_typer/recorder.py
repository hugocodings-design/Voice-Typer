"""Microphone capture into an in-memory float32 buffer."""

import threading
import time

import numpy as np
import sounddevice as sd

_DIRECTSOUND = "Windows DirectSound"


_open_streams = 0          # PortAudio can only be re-scanned while no stream is open
_last_refresh = 0.0
_refresh_lock = threading.Lock()


def refresh_devices(min_interval: float = 5.0) -> bool:
    """Re-scan audio devices: PortAudio only lists those present when it started, so a headset
    plugged in later would stay invisible. Skipped while recording."""
    global _last_refresh
    with _refresh_lock:
        if _open_streams or time.monotonic() - _last_refresh < min_interval:
            return False
        _last_refresh = time.monotonic()
        try:
            sd._terminate()   # noqa: SLF001 — the documented way to re-scan devices
            sd._initialize()  # noqa: SLF001
            return True
        except Exception:  # noqa: BLE001
            return False


def list_microphones(refresh: bool = False) -> list[str]:
    """Input devices with their full names (DirectSound; MME truncates names to 31 chars)."""
    if refresh:
        refresh_devices(min_interval=1.0)
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


def _device_index(name: str | None, refresh: bool = True) -> int | None:
    if not name:
        return None
    i = _find(name)
    if i is None and refresh and refresh_devices():   # maybe plugged in since: look again
        i = _find(name)
    return i  # None: unplugged → Windows default


def _find(name: str) -> int | None:
    try:
        apis = sd.query_hostapis()
        ds = next((i for i, a in enumerate(apis) if a["name"] == _DIRECTSOUND), None)
        for i, d in enumerate(sd.query_devices()):
            if d["name"] == name and d["max_input_channels"] > 0 and (ds is None or d["hostapi"] == ds):
                return i
    except Exception:  # noqa: BLE001
        pass
    return None


class Recorder:
    def __init__(self, sample_rate: int = 16_000):
        self.sample_rate = sample_rate
        self.device_name: str | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self.level = 0.0  # last input loudness (RMS, 0..~1), for the on-screen meter
        self.using_fallback = False  # chosen microphone absent: recording with the Windows default

    def _callback(self, indata, frames, time, status):  # noqa: ARG002
        mono = indata[:, 0]
        self.level = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
        with self._lock:
            self._chunks.append(mono.copy())

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        global _open_streams
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
        device = _device_index(self.device_name)
        self.using_fallback = bool(self.device_name) and device is None
        try:
            stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                                    callback=self._callback, device=device)
        except Exception:  # noqa: BLE001 — chosen mic failed: use the Windows default
            stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                                    callback=self._callback)
            self.using_fallback = bool(self.device_name)
        with _refresh_lock:
            _open_streams += 1
        self._stream = stream
        try:
            stream.start()
        except Exception:
            self._close()
            raise

    def _close(self) -> None:
        global _open_streams
        stream, self._stream = self._stream, None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        finally:
            with _refresh_lock:
                _open_streams = max(0, _open_streams - 1)

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
        self._close()
        self.level = 0.0
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)
