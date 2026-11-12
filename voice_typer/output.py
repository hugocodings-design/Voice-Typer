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
    if keep_in_clipboard:
        clipboard.set_text(text)
        keyboard.send("ctrl+v")
        return
    previous = clipboard.snapshot()          # every format: images, Excel cells, rich text…
    owner = clipboard.offer_delayed(text)    # we'll know when the app actually reads it
    if owner is None:
        clipboard.set_text(text)
    time.sleep(0.03)
    early = owner is not None and owner.rendered.is_set()   # a clipboard manager read it first
    keyboard.send("ctrl+v")
    if previous is None:
        return
    wait_until_pasted(owner, early)
    if owner is not None and clipboard._user32.GetClipboardOwner() != owner.hwnd:
        return   # the user copied something else meanwhile: keep it
    clipboard.restore(previous)


PASTE_TIMEOUT = 2.5     # no paste request after that: the app refused it, restore anyway
AFTER_PASTE = 0.3       # some apps (Teams, new Outlook) read the clipboard twice in a row
FALLBACK_DELAY = 0.6    # when we can't tell (no delayed rendering): a slow app still gets it


def wait_until_pasted(owner, early: bool) -> None:
    if owner is None or early:
        time.sleep(FALLBACK_DELAY)
    elif owner.rendered.wait(PASTE_TIMEOUT):
        time.sleep(AFTER_PASTE)


def copy_selection(timeout: float = 0.6) -> str:
    """Copy the text selected in the focused app (Ctrl+C) and return it; restores the clipboard."""
    previous = clipboard.snapshot()
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
    clipboard.restore(previous)
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
