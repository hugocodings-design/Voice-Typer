"""« Annuler la dernière dictée »: remembers exactly what the last dictation typed, and where.

Undoing sends one Backspace per character typed, so it is only allowed while it is certain to
delete that text and nothing else:
* same window as when the dictation was typed;
* no key typed since (our own shortcuts, modifiers and Esc excepted);
* no mouse click since (a click could have moved the cursor elsewhere in the text);
* within UNDO_WINDOW_S.
Otherwise nothing is deleted and the reason is reported.
"""

import ctypes
import threading
import time
from ctypes import wintypes

UNDO_WINDOW_S = 10 * 60
_IGNORED_KEYS = {"ctrl", "left ctrl", "right ctrl", "shift", "left shift", "right shift", "alt", "left alt",
                 "right alt", "alt gr", "windows", "left windows", "right windows", "esc", "caps lock",
                 "num lock", "scroll lock"}

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetForegroundWindow.restype = wintypes.HWND


def foreground_window() -> int:
    return _user32.GetForegroundWindow() or 0


def char_count(text: str) -> int:
    """Backspaces needed to delete `text` (one per character as apps count them: a Windows
    line break typed as \\r\\n is one character; emoji outside the BMP are one character)."""
    return len(text.replace("\r\n", "\n"))


class UndoTracker:
    def __init__(self, ignored_scan_codes=lambda: set(), clock=time.monotonic):
        self._ignored_scan_codes = ignored_scan_codes   # our shortcuts' keys (callable → set)
        self._clock = clock
        self._lock = threading.Lock()
        self._text = ""
        self._hwnd = 0
        self._at = 0.0
        self._invalid: str | None = "nothing"
        self._suspended = 0
        self._kb_hook = None
        self._mouse = _MouseWatcher(self._on_click)

    # ---- recording what was typed
    def record(self, text: str, hwnd: int | None = None) -> None:
        with self._lock:
            self._text = text
            self._hwnd = foreground_window() if hwnd is None else hwnd
            self._at = self._clock()
            self._invalid = None if text else "nothing"
        if text:
            self._watch()

    def forget(self, reason: str = "nothing") -> None:
        with self._lock:
            self._invalid = reason
            self._text = ""

    def take(self, hwnd: int | None = None) -> tuple[str, str | None]:
        """(text to delete, None) if undo is safe now, else ("", reason). One undo per dictation."""
        hwnd = foreground_window() if hwnd is None else hwnd
        with self._lock:
            if self._invalid:
                return "", self._invalid
            if self._clock() - self._at > UNDO_WINDOW_S:
                return "", "too_old"
            if hwnd != self._hwnd:
                return "", "other_window"
            text, self._text, self._invalid = self._text, "", "done"
            return text, None

    # ---- watching for anything that could have moved the cursor
    def on_key(self, name: str | None, scan_code: int, down: bool = True) -> None:
        if not down or not scan_code or (name or "").lower() in _IGNORED_KEYS:
            return
        if scan_code in self._ignored_scan_codes():
            return
        with self._lock:
            if not self._invalid and not self._suspended:
                self._invalid = "typed_since"

    def _on_click(self) -> None:
        with self._lock:
            if not self._invalid:
                self._invalid = "clicked_since"

    def _watch(self) -> None:
        if self._kb_hook is None:
            try:
                import keyboard

                self._kb_hook = keyboard.hook(
                    lambda e: self.on_key(e.name, e.scan_code, e.event_type == keyboard.KEY_DOWN))
            except Exception:  # noqa: BLE001 — no hook: undo still works, without that guard
                self._kb_hook = None
        self._mouse.start()

    def suspend(self) -> None:
        """While WE type (live typing, the undo itself), our own keystrokes must not count."""
        with self._lock:
            self._suspended += 1

    def resume(self) -> None:
        with self._lock:
            self._suspended = max(0, self._suspended - 1)


# ---------------------------------------------------------------- low-level mouse hook
WH_MOUSE_LL = 14
_CLICKS = {0x0201, 0x0204, 0x0207, 0x020B}   # left / right / middle / X button down
LRESULT = ctypes.c_ssize_t
_HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
_user32.CallNextHookEx.restype = LRESULT
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]


class _MouseWatcher:
    """Calls on_click() on every mouse button press anywhere (never blocks the click)."""

    def __init__(self, on_click):
        self.on_click = on_click
        self._started = False
        self._proc = _HOOKPROC(self._hook)   # keep a reference for the callback's lifetime

    def start(self) -> None:
        if not self._started:
            self._started = True
            threading.Thread(target=self._loop, daemon=True, name="undo-mouse").start()

    def _hook(self, code, wparam, lparam):
        if code >= 0 and wparam in _CLICKS:
            try:
                self.on_click()
            except Exception:  # noqa: BLE001
                pass
        return _user32.CallNextHookEx(None, code, wparam, lparam)

    def _loop(self) -> None:
        if not _user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0):
            return
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
