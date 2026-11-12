"""Windows clipboard with privacy markers.

Text we put on the clipboard is flagged so Windows keeps it out of the clipboard history (Win+V)
and never syncs it to the Microsoft cloud clipboard — dictations can be private (work emails…).
See "Cloud Clipboard and Clipboard History Formats" in the Win32 docs.
"""

import ctypes
import time
from ctypes import wintypes

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.OpenClipboard.argtypes = [wintypes.HWND]
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.EmptyClipboard.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = [wintypes.UINT]
_user32.GetClipboardData.restype = wintypes.HANDLE
_user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_user32.SetClipboardData.restype = wintypes.HANDLE
_user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
_user32.RegisterClipboardFormatW.restype = wintypes.UINT
_user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
_user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
_kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalLock.restype = wintypes.LPVOID
_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

# Format name -> DWORD value (None = the format's presence is the signal)
_PRIVACY_FORMATS = {
    "ExcludeClipboardContentFromMonitorProcessing": None,
    "CanIncludeInClipboardHistory": 0,
    "CanUploadToCloudClipboard": 0,
}


def _open(retries: int = 10) -> bool:
    for _ in range(retries):  # another app may hold the clipboard for a few ms
        if _user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def _alloc(data: bytes) -> int:
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise MemoryError("GlobalAlloc failed")
    ptr = _kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    _kernel32.GlobalUnlock(handle)
    return handle


def get_text() -> str | None:
    if not _open():
        return None
    try:
        if not _user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = _kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


def set_text(text: str, private: bool = True) -> bool:
    """Put text on the clipboard; private=True keeps it out of Win+V history and cloud sync."""
    if not _open():
        return False
    try:
        _user32.EmptyClipboard()
        handle = _alloc((text + "\0").encode("utf-16-le"))
        if not _user32.SetClipboardData(CF_UNICODETEXT, handle):
            _kernel32.GlobalFree(handle)
            return False
        if private:
            for name, value in _PRIVACY_FORMATS.items():
                fmt = _user32.RegisterClipboardFormatW(name)
                data = (value or 0).to_bytes(4, "little")
                h = _alloc(data)
                if not _user32.SetClipboardData(fmt, h):
                    _kernel32.GlobalFree(h)
        return True
    finally:
        _user32.CloseClipboard()


def is_private() -> bool:
    """True if the current clipboard content carries the history/cloud exclusion marker."""
    if not _open():
        return False
    try:
        fmt = _user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
        return bool(_user32.IsClipboardFormatAvailable(fmt))
    finally:
        _user32.CloseClipboard()


# ============================================================ full snapshot / restore (all formats)
# Before pasting a dictation we save EVERYTHING on the clipboard (an image, Excel cells, rich text
# from Word, files copied in Explorer...), not only the plain text, and put it all back afterwards.
CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE = 2, 3, 9, 14
CF_TEXT, CF_OEMTEXT, CF_DIB, CF_LOCALE, CF_DIBV5 = 1, 7, 8, 16, 17
CF_OWNERDISPLAY = 0x0080
# Windows makes these on the fly from another format; restoring the source is enough
_SYNTHESIZED = {CF_TEXT: CF_UNICODETEXT, CF_OEMTEXT: CF_UNICODETEXT, CF_BITMAP: CF_DIB,
                CF_DIBV5: CF_DIB, CF_PALETTE: CF_DIB}
# GDI handles / owner-drawn formats that cannot be copied as bytes
_NOT_COPYABLE = {CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_OWNERDISPLAY, 0x0082, 0x0083, 0x008E}
MAX_SNAPSHOT = 256 * 1024 * 1024   # beyond that (a huge image), only the text is kept

_user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
_user32.EnumClipboardFormats.restype = wintypes.UINT
_user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
_kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalSize.restype = ctypes.c_size_t
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_gdi32.GetEnhMetaFileBits.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p]
_gdi32.GetEnhMetaFileBits.restype = wintypes.UINT
_gdi32.SetEnhMetaFileBits.argtypes = [wintypes.UINT, ctypes.c_char_p]
_gdi32.SetEnhMetaFileBits.restype = wintypes.HANDLE


def sequence() -> int:
    """Changes every time any app puts something on the clipboard."""
    return _user32.GetClipboardSequenceNumber()


def _global_bytes(handle) -> bytes | None:
    size = _kernel32.GlobalSize(handle)
    ptr = _kernel32.GlobalLock(handle)
    if not ptr:
        return None
    try:
        return ctypes.string_at(ptr, size)
    finally:
        _kernel32.GlobalUnlock(handle)


def snapshot() -> list[tuple[int, bytes]] | None:
    """Every format on the clipboard as (format, bytes). [] = empty clipboard, None = unreadable."""
    if not _open():
        return None
    try:
        formats, fmt = [], 0
        while True:
            fmt = _user32.EnumClipboardFormats(fmt)
            if not fmt:
                break
            formats.append(fmt)
        present = set(formats)
        out, total = [], 0
        for fmt in formats:
            if _SYNTHESIZED.get(fmt) in present or fmt in _NOT_COPYABLE:
                continue
            if fmt == CF_LOCALE and CF_UNICODETEXT in present:
                continue
            handle = _user32.GetClipboardData(fmt)
            if not handle:
                continue
            if fmt == CF_ENHMETAFILE:
                n = _gdi32.GetEnhMetaFileBits(handle, 0, None)
                buf = ctypes.create_string_buffer(n)
                data = buf.raw if n and _gdi32.GetEnhMetaFileBits(handle, n, buf) else None
            else:
                data = _global_bytes(handle)
            if data is None:
                continue
            total += len(data)
            if total > MAX_SNAPSHOT:
                return [(f, d) for f, d in out if f == CF_UNICODETEXT]
            out.append((fmt, data))
        return out
    finally:
        _user32.CloseClipboard()


def restore(snap: list[tuple[int, bytes]] | None) -> bool:
    """Puts back what snapshot() saved (None: leave the clipboard alone)."""
    if snap is None:
        return False
    if not _open(retries=100):   # up to ~2 s while the target app still holds the clipboard
        return False
    try:
        _user32.EmptyClipboard()
        for fmt, data in snap:
            if fmt == CF_ENHMETAFILE:
                h = _gdi32.SetEnhMetaFileBits(len(data), data)
                if h:
                    _user32.SetClipboardData(fmt, h)
                continue
            h = _alloc(data or b"\0")
            if not _user32.SetClipboardData(fmt, h):
                _kernel32.GlobalFree(h)
        return True
    finally:
        _user32.CloseClipboard()


# ============================================================ paste with delayed rendering
# To know WHEN the target app has really read the dictation (Outlook / Teams can take a second),
# the text is offered with "delayed rendering": the clipboard only announces "text available",
# and Windows asks our hidden window for it at the exact moment an app pastes (WM_RENDERFORMAT).
WM_RENDERFORMAT, WM_RENDERALLFORMATS = 0x0305, 0x0306
HWND_MESSAGE = wintypes.HWND(-3)
LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", _WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.DefWindowProcW.restype = LRESULT
_user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
_user32.RegisterClassW.restype = wintypes.ATOM
_user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                    wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.GetMessageW.restype = wintypes.BOOL
_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.GetClipboardOwner.restype = wintypes.HWND
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class _DelayedText:
    """Hidden message-only window that owns the clipboard while a dictation is being pasted."""

    def __init__(self):
        import threading

        self.text = ""
        self.rendered = threading.Event()
        self.hwnd = None
        ready = threading.Event()
        self._proc = _WNDPROC(self._wndproc)   # keep a reference: ctypes callbacks must stay alive
        threading.Thread(target=self._loop, args=(ready,), daemon=True, name="clipboard-owner").start()
        ready.wait(5)

    def _loop(self, ready) -> None:
        hinst = _kernel32.GetModuleHandleW(None)
        self._wc = _WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="VoiceTyperClipboardOwner")
        _user32.RegisterClassW(ctypes.byref(self._wc))
        self.hwnd = _user32.CreateWindowExW(0, "VoiceTyperClipboardOwner", None, 0, 0, 0, 0, 0, HWND_MESSAGE,
                                            None, hinst, None)
        ready.set()
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.DispatchMessageW(ctypes.byref(msg))

    def _render(self) -> None:
        h = _alloc((self.text + "\0").encode("utf-16-le"))
        if not _user32.SetClipboardData(CF_UNICODETEXT, h):
            _kernel32.GlobalFree(h)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_RENDERFORMAT and wparam == CF_UNICODETEXT:
            self._render()           # the requesting app has the clipboard open
            self.rendered.set()
            return 0
        if msg == WM_RENDERALLFORMATS:   # our window is going away: leave real data behind
            if _user32.OpenClipboard(hwnd):
                try:
                    if _user32.GetClipboardOwner() == hwnd:
                        self._render()
                finally:
                    _user32.CloseClipboard()
            return 0
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def offer(self, text: str, private: bool = True) -> bool:
        """Announces `text` on the clipboard without handing it over yet."""
        if not self.hwnd:
            return False
        for _ in range(10):
            if _user32.OpenClipboard(self.hwnd):
                break
            time.sleep(0.02)
        else:
            return False
        try:
            _user32.EmptyClipboard()          # makes our window the owner
            self.text = text
            self.rendered.clear()
            _user32.SetClipboardData(CF_UNICODETEXT, None)   # NULL handle = delayed rendering
            if private:
                for name, value in _PRIVACY_FORMATS.items():
                    h = _alloc((value or 0).to_bytes(4, "little"))
                    if not _user32.SetClipboardData(_user32.RegisterClipboardFormatW(name), h):
                        _kernel32.GlobalFree(h)
            return True
        finally:
            _user32.CloseClipboard()


_delayed: "_DelayedText | None" = None


def offer_delayed(text: str, private: bool = True) -> "_DelayedText | None":
    """Puts `text` on the clipboard with delayed rendering; returns the owner (its .rendered event
    fires when an app actually reads the text), or None if that failed (then use set_text)."""
    global _delayed
    try:
        if _delayed is None:
            _delayed = _DelayedText()
        return _delayed if _delayed.offer(text, private) else None
    except Exception:  # noqa: BLE001
        return None
