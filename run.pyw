"""Launcher without a console window: pythonw.exe run.pyw [--minimized]"""

import os
import sys
from pathlib import Path

# pythonw has no console: sys.stdout / sys.stderr are None, and any library that prints
# (e.g. Hugging Face download progress bars) would crash. Send them to a log file instead.
if sys.stdout is None or sys.stderr is None:
    log_dir = Path(os.environ.get("APPDATA", Path.home())) / "VoiceTyper"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "voice_typer.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Our own temporary folder, never %TEMP% (company ASR rules can block it): before anything else runs.
from voice_typer.portable import use_private_temp  # noqa: E402

use_private_temp()

from voice_typer.app import main  # noqa: E402

main()
