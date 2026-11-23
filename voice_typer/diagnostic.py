""""Export a diagnostic": a zip to send when something goes wrong on someone's PC.

Contains the log, the settings (signature and dictionary removed) and system facts.
Never includes dictation history, audio, or the clipboard.
"""

import json
import platform
import sys
import zipfile
from dataclasses import asdict
from datetime import datetime
from importlib import metadata
from pathlib import Path

from voice_typer import __version__, gpu
from voice_typer.config import SETTINGS_DIR

PACKAGES = ["faster-whisper", "ctranslate2", "tokenizers", "huggingface-hub", "sounddevice", "numpy",
            "keyboard", "pystray", "pillow", "sv-ttk", "nvidia-cublas-cu12"]
PRIVATE_FIELDS = {"signature": "<removed>", "signature_en": "<removed>", "home_url": "<removed>", "home_key": "<removed>", "vocabulary": "<removed>", "replacements": "<removed>",
                  "app_dictionaries": "<removed>"}


def system_info(engine=None) -> dict:
    info = {
        "voice_typer": __version__,
        "time": datetime.now().isoformat(timespec="seconds"),
        "windows": platform.platform(),
        "python": sys.version.split()[0],
        "frozen_exe": bool(getattr(sys, "frozen", False)),
        "cpu": platform.processor(),
        "cuda_available": gpu.cuda_available(),
        "gpu": gpu.gpu_name(),
        "packages": {},
    }
    for name in PACKAGES:
        try:
            info["packages"][name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            info["packages"][name] = None
    try:
        import sounddevice as sd

        info["default_input"] = sd.query_devices(kind="input")["name"]
    except Exception as exc:  # noqa: BLE001
        info["default_input"] = f"error: {exc}"
    if engine is not None:
        t = engine.transcriber
        info["speech_model"] = {"source": t.source, "device": t.device, "gpu_error": t.gpu_error} if t else None
        w = engine.writer
        info["writing_model"] = {"source": w.source, "device": w.device, "gpu_error": w.gpu_error} if w else None
    return info


def export(path: str | Path, engine=None) -> Path:
    path = Path(path)
    settings = asdict(engine.config) if engine is not None else {}
    settings.update({k: v for k, v in PRIVATE_FIELDS.items() if k in settings})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.json", json.dumps(system_info(engine), indent=2, ensure_ascii=False))
        z.writestr("settings.json", json.dumps(settings, indent=2, ensure_ascii=False))
        log = SETTINGS_DIR / "voice_typer.log"
        if log.exists():
            z.write(log, "voice_typer.log")
        z.writestr("README.txt", "Voice Typer diagnostic. Contains no dictation history, audio or clipboard "
                                 "content; signature and dictionary are removed from settings.json.\n")
    return path
