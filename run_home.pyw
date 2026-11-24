"""Voice Typer Home without a console window (Start Voice Typer Home.bat, « Démarrer avec Windows »)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if sys.stdout is None or sys.stderr is None:  # pythonw: tracebacks go to the journal folder
    folder = Path(os.environ.get("APPDATA") or Path.home()) / "VoiceTyperHome"
    folder.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(folder / "home-errors.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from home_server.tray_app import run  # noqa: E402

run()
