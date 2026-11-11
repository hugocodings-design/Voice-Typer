"""NVIDIA GPU support for CTranslate2 / faster-whisper.

CTranslate2 ships cuDNN but loads cuBLAS 12 at runtime; it comes from the `nvidia-cublas-cu12`
pip package, whose DLLs live in site-packages/nvidia/*/bin. Those folders are made visible to
the DLL loader here, before any model is created.
"""

import os
import site
import sys
from pathlib import Path

_done = False


def setup_dll_paths() -> None:
    global _done
    if _done or sys.platform != "win32":
        return
    _done = True
    roots = [Path(p) for p in site.getsitepackages()]
    if getattr(sys, "frozen", False):  # installed build (PyInstaller): DLLs sit next to the app
        roots.insert(0, Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
    if site.ENABLE_USER_SITE:
        roots.append(Path(site.getusersitepackages()))
    for root in roots:
        for bin_dir in (root / "nvidia").glob("*/bin"):
            try:
                os.add_dll_directory(str(bin_dir))
            except OSError:
                pass
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        return False


def gpu_name() -> str | None:
    """Best-effort GPU name for display (no extra dependency)."""
    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        name = out.stdout.strip().splitlines()[0].strip() if out.returncode == 0 and out.stdout.strip() else None
        return name or None
    except Exception:  # noqa: BLE001
        return None
