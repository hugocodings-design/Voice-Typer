"""Talking to the copy of Voice Typer that is already running (single instance, see app._already_running).

Launching Voice Typer again (Start menu, desktop shortcut) must simply bring the running copy's window to
the front — often it is hidden next to the clock, where Windows 11 tucks tray icons out of sight. This uses
two named Windows events, never a network port (IT requirement, see tests/test_no_network_server.py):

- SHOW_EVENT: set by the new launch; the running copy waits on it and shows its window;
- ACK_EVENT: set by the running copy *from its tkinter thread* once the window is shown, so a copy whose
  interface is frozen does not answer, and the new launch can offer to close it and start fresh.

The running copy writes its process id to PID_FILE so a frozen copy can be closed (only if that process is
still Voice Typer: same executable name).
"""

import ctypes
import ntpath
import os
import sys
import threading
from ctypes import wintypes

SHOW_EVENT = "VoiceTyper.ShowWindow"
ACK_EVENT = "VoiceTyper.ShowWindowAck"

SYNCHRONIZE = 0x00100000
EVENT_MODIFY_STATE = 0x0002
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WAIT_OBJECT_0 = 0
INFINITE = 0xFFFFFFFF


def _k32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateEventW.restype = wintypes.HANDLE
    k.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    k.OpenEventW.restype = wintypes.HANDLE
    k.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    for name in ("SetEvent", "ResetEvent", "CloseHandle"):
        getattr(k, name).argtypes = (wintypes.HANDLE,)
    k.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    return k


def pid_file():
    from voice_typer.config import SETTINGS_DIR

    return SETTINGS_DIR / "instance.pid"


# ------------------------------------------------------------------ in the running copy
def wait_for_launches(on_show) -> None:
    """Start waiting for a new launch. on_show(ack) is called on a worker thread: it must schedule the
    window on the tkinter thread and call ack() from there once it is shown."""
    try:
        k = _k32()
        show = k.CreateEventW(None, False, False, SHOW_EVENT)   # auto-reset
        ack = k.CreateEventW(None, False, False, ACK_EVENT)
    except Exception:  # noqa: BLE001 — not on Windows: nothing to listen to
        return
    if not show or not ack:
        return
    try:
        p = pid_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(os.getpid()), encoding="ascii")
    except OSError:
        pass

    def loop():
        while k.WaitForSingleObject(show, INFINITE) == WAIT_OBJECT_0:
            try:
                on_show(lambda: k.SetEvent(ack))
            except Exception:  # noqa: BLE001
                pass

    threading.Thread(target=loop, daemon=True, name="instance-show").start()


def forget_pid() -> None:
    try:
        p = pid_file()
        if p.read_text(encoding="ascii").strip() == str(os.getpid()):
            p.unlink()
    except OSError:
        pass


# ------------------------------------------------------------------ in the new launch
def ask_existing_to_show(timeout: float = 4.0) -> bool:
    """True if the running copy showed its window (it answered within `timeout` seconds)."""
    try:
        k = _k32()
    except Exception:  # noqa: BLE001
        return False
    show = k.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT)
    ack = k.OpenEventW(SYNCHRONIZE | EVENT_MODIFY_STATE, False, ACK_EVENT)
    try:
        if not show or not ack:   # a copy from before 0.10, or one stuck before it started listening
            return False
        k.ResetEvent(ack)
        try:  # we are the foreground app (just launched): let the running copy come to the front
            ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
        except Exception:  # noqa: BLE001
            pass
        k.SetEvent(show)
        return k.WaitForSingleObject(ack, int(timeout * 1000)) == WAIT_OBJECT_0
    finally:
        for h in (show, ack):
            if h:
                k.CloseHandle(h)


def _image_name(k, handle) -> str:
    buf = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(len(buf))
    k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD))
    if not k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
        return ""
    return buf.value.rsplit("\\", 1)[-1].lower()


def is_our_executable(image: str) -> bool:
    """Only ever close a process that is Voice Typer itself (a PID can be reused by another program)."""
    image = image.lower()
    if getattr(sys, "frozen", False):
        return image == ntpath.basename(sys.executable).lower()
    return image.startswith(("python", "pythonw"))


def close_frozen_copy() -> bool:
    """Close the unresponsive running copy (the PID it wrote). True if a process was closed."""
    try:
        pid = int(pid_file().read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    try:
        k = _k32()
    except Exception:  # noqa: BLE001
        return False
    h = k.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
    if not h:
        return False
    try:
        if not is_our_executable(_image_name(k, h)):
            return False
        ok = bool(k.TerminateProcess(h, 1))
        if ok:
            k.WaitForSingleObject(h, 5000)
        return ok
    finally:
        k.CloseHandle(h)
