"""Launcher without a console window: pythonw.exe run.pyw [--minimized]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voice_typer.app import main  # noqa: E402

main()
