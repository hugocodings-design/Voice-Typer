"""Start / stop sounds of a dictation.

They used to be `winsound.Beep`, which imitates the old PC speaker through the sound card: after a while, or
when two beeps overlap (quick start/stop, the double beep of a cancel), or with a headset, it crackles and makes
strange noises. Now: a real short tone (WAV made here once, in memory), faded in and out so it never clicks,
played by ONE worker thread so sounds never overlap; if several pile up, the extra ones are dropped.
"""

import io
import math
import queue
import struct
import threading
import wave

RATE = 44100
START, STOP = (880.0, 1175.0), (784.0, 587.0)   # two short notes going up (start) / down (stop)

_queue: queue.Queue = queue.Queue(maxsize=3)
_worker: threading.Thread | None = None
_cache: dict[bool, bytes] = {}


def tone(notes: tuple[float, ...], note_ms: int = 55, volume: float = 0.22, fade_ms: int = 8) -> bytes:
    """A small WAV (16-bit mono) of the given notes, each faded in/out (no clicks)."""
    n = int(RATE * note_ms / 1000)
    fade = max(1, int(RATE * fade_ms / 1000))
    frames = bytearray()
    for freq in notes:
        for i in range(n):
            env = min(1.0, i / fade, (n - 1 - i) / fade)
            frames += struct.pack("<h", int(32767 * volume * env * math.sin(2 * math.pi * freq * i / RATE)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def _play(data: bytes) -> None:
    import winsound

    winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)   # waits until it has played


def _run() -> None:
    while True:
        data = _queue.get()
        try:
            _play(data)
        except Exception:  # noqa: BLE001 — no sound device, sound disabled…: never disturb the dictation
            pass


def play(start: bool) -> None:
    """Non-blocking. Sounds play one after the other, never on top of each other."""
    global _worker
    if start not in _cache:
        _cache[start] = tone(START if start else STOP)
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run, daemon=True, name="sounds")
        _worker.start()
    try:
        _queue.put_nowait(_cache[start])
    except queue.Full:
        pass
