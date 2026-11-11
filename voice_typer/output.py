"""Send transcribed text to the focused application."""

import threading
import time

import keyboard

from voice_typer import clipboard


def send_text(text: str, mode: str = "paste", trailing_space: bool = True, keep_in_clipboard: bool = False) -> None:
    """Type/paste text into the focused app.

    keep_in_clipboard=True leaves the text on the clipboard afterwards (so a stray click can be
    fixed with Ctrl+V); otherwise the previous clipboard content is restored. Either way the
    dictation is flagged private: never in the Win+V history, never synced to the cloud.
    """
    if not text:
        return
    if trailing_space:
        text += " "
    if mode == "type":
        keyboard.write(text)
        if keep_in_clipboard:
            clipboard.set_text(text)
        return
    previous = None if keep_in_clipboard else clipboard.get_text()
    clipboard.set_text(text)
    keyboard.send("ctrl+v")
    time.sleep(0.15)  # let the target app read the clipboard before restoring it
    if previous is not None:
        clipboard.set_text(previous)


def copy_selection(timeout: float = 0.6) -> str:
    """Copy the text selected in the focused app (Ctrl+C) and return it; restores the clipboard."""
    previous = clipboard.get_text()
    marker = f"⁣voice-typer-{time.monotonic()}"  # invisible sentinel: detects "nothing was copied"
    clipboard.set_text(marker)
    keyboard.send("ctrl+c")
    deadline = time.monotonic() + timeout
    text = marker
    while time.monotonic() < deadline:
        time.sleep(0.03)
        text = clipboard.get_text() or ""
        if text != marker:
            break
    if previous is not None:
        clipboard.set_text(previous)
    return "" if text == marker else text


def beep(start: bool) -> None:
    """Short, non-blocking feedback sound."""
    def play():
        try:
            import winsound

            winsound.Beep(880 if start else 620, 70)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=play, daemon=True).start()
