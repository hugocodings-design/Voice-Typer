"""Portable copy (C:\\Dev\\VoiceTyper) and our own temporary folder: %TEMP% is never used."""

import hashlib
import importlib.util
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from voice_typer import portable, updater
from test_updater import PUB, _sign  # shared signing helpers

ROOT = Path(__file__).resolve().parents[1]


def _fake_frozen(monkeypatch, folder: Path, is_portable: bool):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Voice Typer.exe").write_bytes(b"MZ")
    if is_portable:
        (folder / portable.MARKER).write_text("portable")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(folder / "Voice Typer.exe"))


def test_portable_copy_uses_its_own_tmp_folder(monkeypatch, tmp_path):
    app = tmp_path / "Dev" / "VoiceTyper"
    _fake_frozen(monkeypatch, app, is_portable=True)
    assert portable.is_portable()
    assert portable.temp_dir() == app.resolve() / "tmp"


def test_installed_copy_uses_localappdata(monkeypatch, tmp_path):
    _fake_frozen(monkeypatch, tmp_path / "Programs" / "Voice Typer", is_portable=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert not portable.is_portable()
    assert portable.temp_dir() == tmp_path / "Local" / "VoiceTyper" / "tmp"


def test_private_temp_replaces_windows_temp(monkeypatch, tmp_path):
    _fake_frozen(monkeypatch, tmp_path / "app", is_portable=True)
    for name in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(name, str(tmp_path / "WindowsTemp"))
    monkeypatch.setattr(tempfile, "tempdir", None)
    folder = portable.use_private_temp()
    assert folder == (tmp_path / "app").resolve() / "tmp" and folder.is_dir()
    assert os.environ["TEMP"] == os.environ["TMP"] == str(folder)   # inherited by the update installer
    with tempfile.NamedTemporaryFile(delete=False) as f:            # libraries using tempfile follow
        pass
    assert Path(f.name).parent == folder
    Path(f.name).unlink()


def test_portable_zip_layout(tmp_path):
    spec = importlib.util.spec_from_file_location("make_portable", ROOT / "installer" / "make_portable.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = tmp_path / "dist" / "Voice Typer"
    (src / "_internal").mkdir(parents=True)
    (src / "Voice Typer.exe").write_bytes(b"MZ")
    (src / "_internal" / "python312.dll").write_bytes(b"x")
    zip_path = mod.build(src, "9.9.9", tmp_path / "dist")
    assert zip_path.name == "VoiceTyper-portable-9.9.9.zip"
    names = zipfile.ZipFile(zip_path).namelist()
    # extracted straight into C:\Dev\VoiceTyper\ → C:\Dev\VoiceTyper\Voice Typer.exe
    assert set(names) == {"Voice Typer.exe", "_internal/python312.dll", "portable.txt"}


def test_portable_fields_must_point_to_the_releases_repo():
    base = {"version": "9.9.9", "url": updater.ALLOWED_PREFIX + "v9.9.9/VoiceTyperSetup-9.9.9.exe",
            "sha256": "a" * 64, "size": 1}
    good = _sign({**base, "portable_url": updater.ALLOWED_PREFIX + "v9.9.9/VoiceTyper-portable-9.9.9.zip",
                  "portable_sha256": "b" * 64, "portable_size": 2})
    info = updater.validate(good, PUB)
    assert updater.asset(info, portable_copy=True)[0].endswith("VoiceTyper-portable-9.9.9.zip")
    assert updater.asset(info, portable_copy=False)[0].endswith("VoiceTyperSetup-9.9.9.exe")
    bad = _sign({**base, "portable_url": "https://evil.example/x.zip", "portable_sha256": "b" * 64})
    with pytest.raises(updater.UpdateError, match="portable"):
        updater.validate(bad, PUB)
    with pytest.raises(updater.UpdateError, match="no portable package"):
        updater.asset(updater.validate(_sign(base), PUB), portable_copy=True)


def test_portable_download_and_unpack(monkeypatch, tmp_path):
    pkg = tmp_path / "pkg.zip"
    with zipfile.ZipFile(pkg, "w") as z:
        z.writestr("Voice Typer.exe", "MZ new")
        z.writestr("_internal/lib.dll", "x")
    data = pkg.read_bytes()
    monkeypatch.setattr(updater, "DOWNLOAD_DIR", tmp_path / "tmp" / "VoiceTyperUpdate")
    monkeypatch.setattr(portable, "is_portable", lambda: True)

    class Resp:
        headers = {"Content-Length": str(len(data))}

        def __init__(self):
            self._chunks = [data, b""]

        def read(self, _n):
            return self._chunks.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(updater, "_open", lambda url, timeout: Resp())
    info = {"version": "9.9.9", "url": "u", "sha256": "0" * 64, "portable_url": "p",
            "portable_sha256": hashlib.sha256(data).hexdigest(), "portable_size": len(data)}
    path = updater.download(info)
    assert path.name == "VoiceTyper-portable-9.9.9.zip"
    new = updater.unpack_portable(path, "9.9.9")
    assert (new / "Voice Typer.exe").read_text() == "MZ new"
    assert (new / portable.MARKER).is_file()                    # the new version stays portable


def test_unpack_refuses_paths_outside_the_folder(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("Voice Typer.exe", "MZ")
        z.writestr("../../Windows/evil.dll", "x")
    with pytest.raises(updater.UpdateError, match="unsafe"):
        updater.unpack_portable(evil, "9.9.9")


def test_swap_command_copies_over_the_app_then_restarts():
    cmd = updater.portable_swap_command(Path(r"C:\Dev\VoiceTyper\tmp\VoiceTyperUpdate\new-9.9.9"),
                                        Path(r"C:\Dev\VoiceTyper"))
    assert cmd.startswith("ping -n 6 127.0.0.1")                # the app has quit first
    assert 'robocopy "C:\\Dev\\VoiceTyper\\tmp\\VoiceTyperUpdate\\new-9.9.9" "C:\\Dev\\VoiceTyper" /E' in cmd
    assert cmd.endswith('start "" "C:\\Dev\\VoiceTyper\\Voice Typer.exe" --updated')
    assert "%TEMP%" not in cmd and "Temp" not in cmd
