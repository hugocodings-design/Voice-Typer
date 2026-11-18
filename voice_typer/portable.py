"""Where Voice Typer runs from, and its own temporary folder (never Windows' %TEMP%).

Company security rules (Microsoft Defender ASR) can block programs that write to or start from
%TEMP% / AppData\\Local\\Temp. So, at startup, `use_private_temp()` points TEMP / TMP (and Python's tempfile)
to a folder of ours:

- portable copy (a `portable.txt` file next to `Voice Typer.exe`, e.g. unzipped to C:\\Dev\\VoiceTyper\\):
  `<app folder>\\tmp`;
- installed copy: `%LOCALAPPDATA%\\VoiceTyper\\tmp`.

Every library and every program we start (the update installer, whose helper Inno Setup unpacks in TMP)
inherits it. The app itself is a PyInstaller *folder* build: it never unpacks anything at startup.
"""

import os
import sys
import tempfile
from pathlib import Path

MARKER = "portable.txt"


def app_dir() -> Path:
    """Folder holding Voice Typer.exe (packaged), or the source checkout."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def is_portable() -> bool:
    return bool(getattr(sys, "frozen", False)) and (app_dir() / MARKER).is_file()


def temp_dir() -> Path:
    if is_portable():
        return app_dir() / "tmp"
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "VoiceTyper" / "tmp"


def use_private_temp() -> Path | None:
    """Call first thing at startup. Returns the folder used (None if it could not be created)."""
    folder = temp_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None  # read-only location: keep the system default rather than fail to start
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(folder)
    tempfile.tempdir = str(folder)
    return folder
