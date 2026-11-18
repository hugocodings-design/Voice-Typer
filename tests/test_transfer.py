"""Settings export / import between PCs (transfer.py)."""

import json

import pytest

from voice_typer import transfer
from voice_typer.config import Config


def _mine() -> Config:
    cfg = Config()
    cfg.ensure_presets()
    cfg.vocabulary = ["Gagnon", "Desjardins"]
    cfg.replacements = [{"from": "mtl", "to": "Montréal"}]
    cfg.app_dictionaries = [{"app": "outlook.exe", "vocabulary": ["MTL inc."], "replacements": []}]
    cfg.signature = "Hugo"
    cfg.hotkey = "f9"
    cfg.undo_hotkey = "ctrl+alt+z"
    cfg.model = "bofenghuang/whisper-large-v3-french-distil-dec2#ctranslate2"
    cfg.custom_models = [{"label": "HF", "source": "org/model"}, {"label": "local", "source": r"C:\Models\x"}]
    cfg.ui_language = "en"
    # machine-specific: must never travel
    cfg.input_device = "Jabra Evolve"
    cfg.skipped_update = "0.9.9"
    return cfg


def test_roundtrip_carries_user_work(tmp_path):
    path = tmp_path / "s.json"
    transfer.export_settings(_mine(), path)
    other = Config()
    other.input_device = "Realtek"
    changed = transfer.apply_settings(other, transfer.read_export(path))
    assert other.vocabulary == ["Gagnon", "Desjardins"]
    assert other.replacements == [{"from": "mtl", "to": "Montréal"}]
    assert other.app_dictionaries[0]["app"] == "outlook.exe"
    assert other.signature == "Hugo" and other.hotkey == "f9" and other.undo_hotkey == "ctrl+alt+z"
    assert other.model.startswith("bofenghuang/")
    assert other.ui_language == "en"
    assert other.presets and all("id" in p for p in other.presets)
    assert "vocabulary" in changed and "input_device" not in changed
    assert other.input_device == "Realtek"


def test_machine_specific_and_secrets_stay(tmp_path):
    path = tmp_path / "s.json"
    transfer.export_settings(_mine(), path)
    raw = path.read_text(encoding="utf-8")
    for secret in ("Jabra", "0.9.9", "first_run_done"):
        assert secret not in raw
    data = json.loads(raw)["settings"]
    assert data["custom_models"] == [{"label": "HF", "source": "org/model"}]  # local folder dropped


def test_local_model_folder_not_exported(tmp_path):
    cfg = _mine()
    cfg.model = str(tmp_path)  # an existing folder on this PC
    path = tmp_path / "s.json"
    transfer.export_settings(cfg, path)
    assert "model" not in json.loads(path.read_text(encoding="utf-8"))["settings"]


def test_import_rejects_paths_and_bad_types(tmp_path):
    doc = {"format": transfer.FORMAT, "format_version": 1, "settings": {
        "model": r"D:\Models\whisper",           # another PC's folder
        "hotkey": 5,                             # wrong type
        "trailing_space": "yes",                 # wrong type
        "sounds": False,                         # ok
        "vocabulary": ["ok", 3],                 # bad item
        "replacements": [{"from": "a"}],         # missing "to"
        "host_key": "evil", "remote_url": "https://1.2.3.4:8765",  # PC boost pairing: never imported
        "language": "de",                        # valid type, normalised on apply
    }}
    path = tmp_path / "s.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    settings = transfer.read_export(path)
    assert set(settings) == {"sounds", "language"}
    cfg = Config()
    transfer.apply_settings(cfg, settings)
    assert cfg.sounds is False and cfg.language is None
    # a settings file must never connect this PC to another computer (it would send it the audio)
    assert cfg.host_key == "" and cfg.remote_url == "" and cfg.remote_mode == "off"


@pytest.mark.parametrize("content,key", [
    ("not json", "xfer_bad_file"),
    (json.dumps({"hello": 1}), "xfer_bad_file"),
    (json.dumps({"format": "voice-typer-settings", "format_version": 99, "settings": {}}), "xfer_too_new"),
])
def test_bad_files(tmp_path, content, key):
    path = tmp_path / "s.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(transfer.ImportError_) as err:
        transfer.read_export(path)
    assert str(err.value) == key


def test_missing_file(tmp_path):
    with pytest.raises(transfer.ImportError_):
        transfer.read_export(tmp_path / "nope.json")


def test_same_settings_change_nothing(tmp_path):
    cfg = _mine()
    path = tmp_path / "s.json"
    transfer.export_settings(cfg, path)
    settings = transfer.read_export(path)
    assert transfer.changes(cfg, settings) == []
    assert transfer.apply_settings(cfg, settings) == []
    assert {"label": "local", "source": r"C:\Models\x"} in cfg.custom_models  # this PC's local model kept


def test_restart_command_runs_module():
    from voice_typer.app import restart_command

    cmd = restart_command()
    assert cmd[-1] == "--restart" and "voice_typer" in cmd


def test_restart_waits_for_the_previous_copy(monkeypatch):
    import subprocess
    import sys
    import time

    from voice_typer import app

    name = f"VoiceTyper.Test.{time.monotonic_ns()}"
    monkeypatch.setattr(app, "MUTEX_NAME", name)
    code = (f"import ctypes,time;ctypes.windll.kernel32.CreateMutexW(None,False,{name!r});"
            "print('held',flush=True);time.sleep(1.0)")
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        holder.stdout.readline()
        assert app._already_running() is True              # a normal second launch is refused
        t0 = time.monotonic()
        assert app._already_running(wait=8.0) is False     # a restart waits for it to close
        assert time.monotonic() - t0 < 4.0
    finally:
        holder.kill()
