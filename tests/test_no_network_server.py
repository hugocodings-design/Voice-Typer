"""Power sharing was removed (0.9.3): the app must never listen on a network port,
and an update from an older version must clean up what sharing left behind."""

import json
import pkgutil
import re
import socket
from pathlib import Path

import pytest

import voice_typer
from voice_typer import config as config_mod, legacy

SRC = Path(voice_typer.__file__).parent


def test_source_has_no_server_code():
    pattern = re.compile(r"\.listen\(|\.bind\(\(|HTTPServer|socketserver|\.accept\(|create_server")
    hits = [f"{f.relative_to(SRC)}: {m.group(0)}" for f in SRC.rglob("*.py")
            for m in pattern.finditer(f.read_text(encoding="utf-8"))]
    assert hits == []


def test_no_listening_socket_at_runtime(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(socket.socket, "listen", lambda self, *a: opened.append(("listen", a)))
    monkeypatch.setattr(socket.socket, "bind", lambda self, addr: opened.append(("bind", addr)))
    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    for mod in pkgutil.walk_packages(voice_typer.__path__, "voice_typer."):
        if mod.name.endswith("__main__"):
            continue
        __import__(mod.name)
    from voice_typer import app, undo

    monkeypatch.setattr(undo.UndoTracker, "_watch", lambda self: None)
    cfg = config_mod.Config()
    cfg.writer_preload = False
    eng = app.Engine(cfg)
    monkeypatch.setattr(eng, "load_model", lambda source: None)
    monkeypatch.setattr(eng, "resume_hotkey", lambda: None)
    eng.start()
    eng.stop()
    assert opened == []


def _old_install(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    for name in legacy.OLD_FILES:
        (tmp_path / name).write_text("x", encoding="utf-8")
    settings = {"hotkey": "alt+1", "mode": "hold", "remote_mode": "client", "remote_url": "https://100.1.2.3:8765",
                "remote_key": "k", "remote_fingerprint": "ab", "host_key": "s", "host_port": 8765,
                "host_allow_internet": False, "client_id": "c", "first_run_done": True}
    (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


def test_update_from_power_sharing_version(tmp_path, monkeypatch):
    _old_install(tmp_path, monkeypatch)
    cfg = config_mod.Config.load()               # old keys ignored without error
    assert cfg.hotkey == "alt+1" and not hasattr(cfg, "remote_mode")
    result = legacy.remove_power_sharing()
    assert sorted(result["files"]) == sorted(legacy.OLD_FILES)
    assert set(result["settings"]) == set(legacy.OLD_KEYS)
    assert not any((tmp_path / n).exists() for n in legacy.OLD_FILES)
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["hotkey"] == "alt+1" and not set(legacy.OLD_KEYS) & set(data)
    assert legacy.remove_power_sharing()["done_before"]   # only once


def test_client_mode_copy_transcribes_locally(tmp_path, monkeypatch):
    _old_install(tmp_path, monkeypatch)
    from voice_typer import app, undo

    monkeypatch.setattr(undo.UndoTracker, "_watch", lambda self: None)
    eng = app.Engine(config_mod.Config.load())
    assert not hasattr(eng, "remote") and not hasattr(eng, "apply_remote")


def test_firewall_cleanup_only_targets_the_installed_app(monkeypatch):
    monkeypatch.setattr(legacy.sys, "frozen", False, raising=False)
    assert legacy.firewall_rules() == []     # from source: never touches python.exe rules
    script = legacy._rules_script([r"C:\Users\O'Brien\AppData\Local\Programs\Voice Typer\Voice Typer.exe"])
    assert "o''brien" in script and "Get-NetFirewallApplicationFilter" in script
    assert legacy._remove_script(["{abc}", "x'y"]) == \
        "Remove-NetFirewallRule -Name @('{abc}','x''y') -ErrorAction SilentlyContinue"


@pytest.mark.parametrize("names, left", [([], [])])
def test_remove_rules_noop_without_rules(names, left):
    assert legacy.remove_rules(names) == left
