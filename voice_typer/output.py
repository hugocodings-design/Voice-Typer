"""Send transcribed text to the focused application."""

import threading
import time

import keyboard
import pyperclip


def send_text(text: str, mode: str = "paste", trailing_space: bool = True, keep_in_clipboard: bool = False) -> None:
    """Type/paste text into the focused app.

    keep_in_clipboard=True leaves the text on the clipboard afterwards (so a stray click can be
    fixed with Ctrl+V); otherwise the previous clipboard content is restored.
    """
    if not text:
        return
    if trailing_space:
        text += " "
    if mode == "type":
        keyboard.write(text)
        if keep_in_clipboard:
            _copy(text)
        return
    previous = None
    if not keep_in_clipboard:
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            pass
    _copy(text)
    keyboard.send("ctrl+v")
    time.sleep(0.15)  # let the target app read the clipboard before restoring it
    if previous is not None:
        _copy(previous)


def _copy(text: str) -> None:
    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException:
        pass


def beep(start: bool) -> None:
    """Short, non-blocking feedback sound."""
    def play():
        try:
            import winsound

            winsound.Beep(880 if start else 620, 70)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=play, daemon=True).start()
