"""How full the home PC's graphics card memory is (nvidia-smi, installed with every NVIDIA driver).

Why it matters: when the 8 GB are full, Windows' NVIDIA driver often does NOT fail — it quietly moves the
overflow to the PC's ordinary memory and the card becomes 10–15× slower ("transcription 5,5 s (maison)" for 6 s
of audio). Seeing "7,9 / 8,0 Go — pleine" tells the user to close what uses the card or pick lighter models.
"""

import os
import subprocess
import threading
import time

FULL_RATIO = 0.92        # above this, the driver starts spilling into ordinary memory
SLOW_RATIO = 0.35        # transcription slower than this × the audio length, on the card = not normal


def parse(output: str) -> tuple[int, int] | None:
    """'7890, 8192' (MiB used, total) of the first card → (7890, 8192)."""
    for line in output.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 2 and all(p.isdigit() for p in parts) and int(parts[1]) > 0:
            return int(parts[0]), int(parts[1])
    return None


def read() -> tuple[int, int] | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse(out.stdout) if out.returncode == 0 else None


def is_full(used: int, total: int) -> bool:
    return total > 0 and used / total >= FULL_RATIO


def gb(mib: int) -> str:
    return f"{mib / 1024:.1f}".replace(".", ",")


def describe(used: int, total: int) -> str:
    """« Mémoire graphique : 7,9 / 8,0 Go — PLEINE (lent) »."""
    text = f"Mémoire graphique : {gb(used)} / {gb(total)} Go"
    return text + (" — PLEINE (lent)" if is_full(used, total) else "")


class Monitor:
    """Reads the memory at most every `every` seconds (pings and the tray menu ask often)."""

    def __init__(self, reader=read, every: float = 10.0, clock=time.monotonic):
        self.reader, self.every, self.clock = reader, every, clock
        self._value: tuple[int, int] | None = None
        self._at = -1e9
        self._lock = threading.Lock()

    def get(self) -> tuple[int, int] | None:
        with self._lock:
            if self.clock() - self._at >= self.every:
                self._value = self.reader()
                self._at = self.clock()
            return self._value
