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
