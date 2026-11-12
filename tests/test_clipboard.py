"""Clipboard (Windows only): privacy markers, full save/restore, paste timing.
Puts the user's clipboard back afterwards (all formats)."""

import sys
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows clipboard")


@pytest.fixture
def clip():
    from voice_typer import clipboard

    saved = clipboard.snapshot()
    yield clipboard
    clipboard.restore(saved)


def _put(clip, items):
    """Puts several raw formats on the clipboard, like Word or Excel would."""
    assert clip._open()
    try:
        clip._user32.EmptyClipboard()
        for fmt, data in items:
            clip._user32.SetClipboardData(fmt, clip._alloc(data))
    finally:
        clip._user32.CloseClipboard()


def _rich(clip):
    html = clip._user32.RegisterClipboardFormatW("HTML Format")
    custom = clip._user32.RegisterClipboardFormatW("VoiceTyper Test Cells")
    # tiny 1x1 24-bit DIB (BITMAPINFOHEADER + one pixel padded to 4 bytes)
    dib = (40).to_bytes(4, "little") + (1).to_bytes(4, "little") + (1).to_bytes(4, "little") + \
        (1).to_bytes(2, "little") + (24).to_bytes(2, "little") + bytes(24) + b"\x10\x20\x30\x00"
    return [(clip.CF_UNICODETEXT, "Copié dans Word\0".encode("utf-16-le")),
            (html, b"Version:0.9\r\n<b>gras</b>\0"), (custom, b"\x01\x02\x03\x00binary"), (clip.CF_DIB, dib)]


def _formats(snap):
    return {f: d for f, d in snap}


def test_private_roundtrip(clip):
    assert clip.set_text("Bonjour Madame Gagnon, é à ç — test")
    assert clip.get_text() == "Bonjour Madame Gagnon, é à ç — test"
    assert clip.is_private()


def test_non_private(clip):
    assert clip.set_text("public", private=False)
    assert clip.get_text() == "public"
    assert not clip.is_private()


def test_snapshot_restores_every_format(clip):
    items = _rich(clip)
    _put(clip, items)
    snap = clip.snapshot()
    clip.set_text("dictée")
    assert clip.restore(snap)
    got = _formats(clip.snapshot())
    for fmt, data in items:
        assert got[fmt][:len(data)] == data, fmt   # GlobalSize may round the size up


def test_delayed_rendering_signals_the_paste(clip):
    owner = clip.offer_delayed("texte dicté")
    assert owner is not None and not owner.rendered.is_set()
    assert clip.get_text() == "texte dicté"          # an app reads it → Windows asks our window
    assert owner.rendered.is_set()
    assert clip.is_private()


def _app_read(clip):
    """Reads the clipboard like a real app does: through one of its windows (seen by GetOpenClipboardWindow)."""
    import ctypes

    u32 = ctypes.windll.user32
    u32.CreateWindowExW.restype = ctypes.c_void_p
    u32.CreateWindowExW.argtypes = [ctypes.c_ulong, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong] + \
        [ctypes.c_int] * 4 + [ctypes.c_void_p] * 4
    k32 = ctypes.windll.kernel32
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.GetClipboardData.restype = ctypes.c_void_p
    hwnd = u32.CreateWindowExW(0, "STATIC", "fake app", 0, 0, 0, 0, 0, ctypes.c_void_p(-3), None, None, None)
    try:
        for _ in range(50):
            if u32.OpenClipboard(ctypes.c_void_p(hwnd)):
                break
            time.sleep(0.01)
        try:
            time.sleep(0.02)  # apps hold it open a moment
            h = u32.GetClipboardData(clip.CF_UNICODETEXT)
            p = k32.GlobalLock(h) if h else None
            text = ctypes.wstring_at(p) if p else None
            if p:
                k32.GlobalUnlock(h)
            return text
        finally:
            u32.CloseClipboard()
    finally:
        u32.DestroyWindow(ctypes.c_void_p(hwnd))


def _slow_app(clip, delay, seen):
    """keyboard.send replacement: the 'app' reads the clipboard `delay` s after Ctrl+V (Outlook…)."""
    def send(keys):
        assert keys == "ctrl+v"
        threading.Timer(delay, lambda: seen.append(_app_read(clip))).start()
    return send


@pytest.mark.parametrize("sync_tool", [False, True])
def test_slow_app_gets_the_dictation_and_clipboard_is_restored(clip, monkeypatch, sync_tool):
    """sync_tool: an Android emulator / Phone Link / clipboard manager reads every new clipboard at once."""
    import os

    from voice_typer import output

    items = _rich(clip)
    _put(clip, items)
    seen = []
    monkeypatch.setattr(output.keyboard, "send", _slow_app(clip, 0.9, seen))   # 6x the old fixed 0.15 s
    monkeypatch.setattr(output, "_foreground_pid", lambda: os.getpid())         # the fake app is "focused"
    if sync_tool:
        offer = clip.offer_delayed

        def offer_and_get_read(text):
            owner = offer(text)
            clip.get_text()
            return owner
        monkeypatch.setattr(clip, "offer_delayed", offer_and_get_read)
    t0 = time.perf_counter()
    output.send_text("Bonjour", trailing_space=False)
    time.sleep(0.05)
    assert seen == ["Bonjour"]
    assert time.perf_counter() - t0 < 2.0             # restored soon after the app read it, not at the timeout
    got = _formats(clip.snapshot())
    for fmt, data in items:
        assert got[fmt][:len(data)] == data


def test_app_that_never_pastes_still_gets_clipboard_back(clip, monkeypatch):
    from voice_typer import output

    clip.set_text("avant", private=False)
    monkeypatch.setattr(output.keyboard, "send", lambda keys: None)
    monkeypatch.setattr(output, "PASTE_TIMEOUT", 0.3)
    output.send_text("perdu", trailing_space=False)
    assert clip.get_text() == "avant"


def test_user_copy_during_paste_is_kept(clip, monkeypatch):
    from voice_typer import output

    clip.set_text("avant", private=False)

    def send(keys):   # the user copies something else before the app reads the dictation
        threading.Timer(0.1, lambda: clip.set_text("copie de l'utilisateur", private=False)).start()

    monkeypatch.setattr(output.keyboard, "send", send)
    monkeypatch.setattr(output, "PASTE_TIMEOUT", 0.5)
    output.send_text("dictée", trailing_space=False)
    assert clip.get_text() == "copie de l'utilisateur"


def test_copy_selection_restores_everything(clip, monkeypatch):
    from voice_typer import output

    items = _rich(clip)
    _put(clip, items)
    monkeypatch.setattr(output.keyboard, "send", lambda keys: clip.set_text("texte sélectionné"))
    assert output.copy_selection() == "texte sélectionné"
    got = _formats(clip.snapshot())
    for fmt, data in items:
        assert got[fmt][:len(data)] == data
