"""Send transcribed text to the focused application."""

import time

import keyboard
import pyperclip


def send_text(text: str, mode: str = "paste") -> None:
    if not text:
        return
    if mode == "type":
        keyboard.write(text + " ")
        return
    # Paste mode: put text on the clipboard, press ctrl+v, then restore the previous clipboard.
    previous = None
    try:
        previous = pyperclip.paste()
    except pyperclip.PyperclipException:
        pass
    pyperclip.copy(text + " ")
    keyboard.send("ctrl+v")
    time.sleep(0.15)  # let the target app read the clipboard before restoring it
    if previous is not None:
        pyperclip.copy(previous)
