"""Send transcribed text to the focused application."""

import ctypes
import time
from ctypes import wintypes

import keyboard

from voice_typer import clipboard

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetOpenClipboardWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(ctypes.c_ulong)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD


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
    # Clipboard sync tools (Android emulator, Phone Link, Remote Desktop, clipboard managers) read
    # every new clipboard within ~2 ms: the delayed rendering then no longer tells us when the app
    # pasted, so we watch the target app open the clipboard instead.
    early = owner is not None and owner.rendered.is_set()
    target = _foreground_pid()
    keyboard.send("ctrl+v")
    if previous is None:
        return
    wait_until_pasted(owner, early, target)
    if owner is not None and clipboard._user32.GetClipboardOwner() != owner.hwnd:
        return   # the user copied something else meanwhile: keep it
    clipboard.restore(previous)


PASTE_TIMEOUT = 2.5     # no paste seen after that: the app refused it, restore anyway
AFTER_PASTE = 0.3       # some apps (Teams, new Outlook) read the clipboard twice in a row
FALLBACK_DELAY = 0.6    # when we can't tell at all: a slow app still gets it


def _pid_of(hwnd) -> int | None:
    if not hwnd:
        return None
    pid = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None


def _foreground_pid() -> int | None:
    return _pid_of(_user32.GetForegroundWindow())


def _clipboard_reader_pid() -> int | None:
    """Process that has the clipboard open right now (None if nobody, or opened without a window)."""
    return _pid_of(_user32.GetOpenClipboardWindow())


def wait_until_pasted(owner, early: bool, target_pid: int | None = None) -> None:
    deadline = time.monotonic() + PASTE_TIMEOUT
    if owner is not None and not early:
        if not owner.rendered.wait(PASTE_TIMEOUT):
            return
        reader = _pid_of(owner.reader_hwnd)
        if reader is None or not target_pid or reader == target_pid:
            time.sleep(AFTER_PASTE)
            return
        # read by another program (a sync tool that was a bit slower), not by the app: keep watching
    elif not target_pid:
        time.sleep(FALLBACK_DELAY)
        return
    while time.monotonic() < deadline:
        if _clipboard_reader_pid() == target_pid:   # the focused app is reading the dictation
            time.sleep(AFTER_PASTE)
            return
        time.sleep(0.002)


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
    """Short, non-blocking feedback sound (sounds.py: a real tone, never winsound.Beep)."""
    from voice_typer import sounds

    sounds.play(start)
