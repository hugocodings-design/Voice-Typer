"""« Signaler un problème »: prepares an e-mail to the developer with a diagnostic attached.

1. diagnostic.export() writes a zip to the Downloads folder (log, settings without private fields, system
   facts — never dictation history, audio or clipboard);
2. classic Outlook (most work PCs) opens a new message with the address, subject, the user's description
   AND the zip attached (`outlook.exe /c ipm.note /m … /a <zip>`);
3. otherwise the default mail app opens through mailto: (attachments are impossible there) and the folder
   holding the zip is shown, so the user can attach it.

No network access of our own: the user's mail app sends the message, and the user sees it before sending.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from voice_typer import __version__

SUPPORT_EMAIL = "hugocodings@gmail.com"


def downloads_dir() -> Path:
    for d in (Path.home() / "Downloads", Path.home() / "Desktop", Path.home()):
        if d.is_dir():
            return d
    return Path.home()


def subject() -> str:
    return f"Voice Typer {__version__} — problème"


def body(description: str, zip_name: str, attached: bool) -> str:
    lines = [description.strip() or "(décrivez le problème ici)", "", "—", f"Voice Typer {__version__}"]
    try:
        import platform

        lines.append(platform.platform())
    except Exception:  # noqa: BLE001
        pass
    lines.append(f"Diagnostic : {zip_name}" + ("" if attached else " (à joindre à ce courriel)"))
    return "\n".join(lines)


def mailto_url(description: str, zip_name: str, attached: bool) -> str:
    return (f"mailto:{SUPPORT_EMAIL}?subject={quote(subject())}"
            f"&body={quote(body(description, zip_name, attached))}")


def outlook_path() -> str | None:
    """Classic Outlook's exe from the registry (the new Outlook has no command line for attachments)."""
    try:
        import winreg
    except ImportError:
        return None
    key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key) as k:
                path = winreg.QueryValueEx(k, "")[0]
                if path and os.path.isfile(path):
                    return path
        except OSError:
            continue
    return None


def outlook_command(outlook: str, description: str, zip_path: Path) -> list[str]:
    # /m takes "address&subject=…&body=…" (URL-encoded), /a attaches a file to the new message
    m = f"{SUPPORT_EMAIL}&subject={quote(subject())}&body={quote(body(description, zip_path.name, True))}"
    return [outlook, "/c", "ipm.note", "/m", m, "/a", str(zip_path)]


def prepare(engine, description: str) -> tuple[Path, str]:
    """Writes the diagnostic and opens the e-mail. Returns (zip path, "outlook" | "mailto" | "none")."""
    from voice_typer import diagnostic

    path = downloads_dir() / f"VoiceTyper-probleme-{datetime.now():%Y%m%d-%H%M%S}.zip"
    diagnostic.export(path, engine)
    outlook = outlook_path()
    if outlook:
        try:
            subprocess.Popen(outlook_command(outlook, description, path), close_fds=True)  # noqa: S603
            return path, "outlook"
        except OSError:
            pass
    reveal(path)
    try:
        os.startfile(mailto_url(description, path.name, attached=False))  # type: ignore[attr-defined]
        return path, "mailto"
    except (OSError, AttributeError):
        return path, "none"


def reveal(path: Path) -> None:
    """Show the file selected in Explorer, so it can be dragged into the e-mail."""
    if sys.platform != "win32":
        return
    try:
        subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603, S607
    except OSError:
        pass
