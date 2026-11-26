"""« PC à la maison »: the work PC is only a client (voice_typer/home.py); Home Connections (its own repo)
runs on the home PC and has the server tests."""

import json
import zlib

import numpy as np
import pytest

from voice_typer import home

KEY = "k" * 43


def test_url_must_be_https():
    assert home.normalize_url("home-pc.tail1234.ts.net/") == "https://home-pc.tail1234.ts.net"
    assert home.normalize_url("http://127.0.0.1:8765") == "http://127.0.0.1:8765"   # tests / same PC only
    with pytest.raises(home.HomeError, match="https_required"):
        home.normalize_url("http://home-pc.tail1234.ts.net")
    with pytest.raises(home.HomeError, match="not_configured"):
        home.HomeClient("", "key")


def test_audio_round_trip_and_zip_bomb():
    audio = np.sin(np.linspace(0, 100, 16000)).astype(np.float32) * 0.5
    back = home.decode_audio(home.encode_audio(audio), 16000 * 2)
    assert np.abs(back - audio).max() < 1e-3
    bomb = zlib.compress(b"\0" * (50 * 1024 * 1024))
    with pytest.raises(ValueError):
        home.decode_audio(bomb, 1024 * 1024)


def test_work_package_has_no_server_code():
    """The server lives in Home Connections: nothing of it in this repo, nothing listens here."""
    from pathlib import Path

    import voice_typer
    src = Path(voice_typer.__file__).parent
    assert not (src.parent / "home_server").exists() and not (src / "home_server").exists()
    code = "".join(p.read_text(encoding="utf-8") for p in src.rglob("*.py"))
    assert "import home_server" not in code and "from home_server" not in code


class Answer:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def read(self, n=-1):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_client_names_itself_and_wakes_models(monkeypatch):
    sent = []
    monkeypatch.setattr(home, "_open", lambda req, timeout: sent.append(req) or Answer({"ok": True, "waking": ["whisper"]}))
    client = home.HomeClient("hugo.tail1.ts.net", KEY)
    assert client.wake({"whisper": "large-v3-turbo"})["waking"] == ["whisper"]
    req = sent[0]
    assert req.full_url == "https://hugo.tail1.ts.net/v1/wake" and req.get_header("X-app") == "voicetyper-pc"
    assert json.loads(req.data) == {"models": {"whisper": "large-v3-turbo"}}
    assert req.get_header("Authorization") == f"Bearer {KEY}"


class FakeEngine:
    """Just enough of Engine for HomeMixin."""

    def __init__(self, cfg):
        from voice_typer.engine_home import HomeMixin

        self.__class__ = type("E", (FakeEngine, HomeMixin), {})
        self.config, self.events = cfg, []
        self.transcriber = type("T", (), {"device": "cuda"})()
        self.writer = type("W", (), {"device": "cuda"})()
        self.loading_source = None
        self.writer_loading = False
        self.preset_hotkeys = {"email": object()}
        self.loaded = []
        self._home_init()

    def _emit(self, kind, payload=None):
        self.events.append((kind, payload))

    def load_model(self, source, device=None):
        self.loaded.append((source, device))

    def unload_writer(self):
        self.writer = None


def test_home_pc_uses_its_own_voice_typer_home(monkeypatch):
    """On the home PC: Voice Typer finds Voice Typer Home (key file) and stops using the graphics card."""
    from voice_typer import engine_home
    from voice_typer.config import Config

    monkeypatch.setattr(engine_home, "local_home_key", lambda: KEY)
    monkeypatch.setattr(home.HomeClient, "ping", lambda self: {"device": "cuda", "writer_device": "cuda"})
    eng = FakeEngine(Config())
    eng._check_home()
    assert eng.home_client().url == engine_home.LOCAL_URL
    assert eng.model_device() == "cpu" and eng.loaded == [(eng.config.model, "cpu")] and eng.writer is None
    assert ("home_status", {"state": "ok", "local": True, "device": "cuda", "writer_device": "cuda"}) in eng.events


def test_home_connections_key_comes_first(monkeypatch, tmp_path):
    from voice_typer import engine_home

    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert engine_home.local_home_key() == ""
    (tmp_path / "VoiceTyperHome").mkdir()
    (tmp_path / "VoiceTyperHome" / "key.txt").write_text("old-key")
    assert engine_home.local_home_key() == "old-key"
    (tmp_path / "HomeConnections").mkdir()
    (tmp_path / "HomeConnections" / "key.txt").write_text("shared-key  ")
    assert engine_home.local_home_key() == "shared-key"


def test_recording_wakes_the_home_pc(monkeypatch):
    from voice_typer import engine_home
    from voice_typer.config import Config

    cfg = Config()
    cfg.home_enabled, cfg.home_url, cfg.home_key = True, "hugo.tail1.ts.net", KEY
    cfg.model, cfg.writing_model = "large-v3-turbo", "qwen-3b"
    monkeypatch.setattr(engine_home, "local_home_key", lambda: "")
    asked = []
    monkeypatch.setattr(home.HomeClient, "wake", lambda self, models: asked.append(models))
    monkeypatch.setattr(engine_home.threading, "Thread", lambda target, daemon: type("T", (), {"start": staticmethod(target)})())
    eng = FakeEngine(cfg)
    eng.wake_home(None)
    eng.wake_home("email")                                       # a preset needs the writing AI too
    assert asked == [{"whisper": "large-v3-turbo"}, {"whisper": "large-v3-turbo", "writer": "qwen-3b"}]
    eng.home_info = {"state": "down"}
    eng.wake_home(None)                                          # unreachable: don't try at each dictation
    cfg.home_enabled = False
    eng.home_info = {"state": "ok"}
    eng.wake_home(None)
    assert len(asked) == 2


def test_status_of_the_configured_home_pc(monkeypatch):
    from voice_typer import engine_home
    from voice_typer.config import Config

    cfg = Config()
    cfg.home_enabled, cfg.home_url, cfg.home_key = True, "hugo.tail1.ts.net", KEY
    monkeypatch.setattr(engine_home, "local_home_key", lambda: "")

    def down(self):
        raise home.HomeError("unreachable")

    monkeypatch.setattr(home.HomeClient, "ping", down)
    eng = FakeEngine(cfg)
    eng._check_home()
    assert eng.home_info == {"state": "down", "reason": "unreachable", "local": False}
    assert eng.loaded == []                                      # a remote home PC never moves local models
    eng._home_result(True, writer_device="cpu")                 # a dictation went through, AI on its processor
    assert eng.home_info["state"] == "ok" and eng.home_info["writer_device"] == "cpu"
    assert eng.writer is None                                   # the laptop's own AI copy is freed meanwhile
    assert eng.model_device() is None


def test_nothing_happens_without_home(monkeypatch):
    from voice_typer import engine_home
    from voice_typer.config import Config

    monkeypatch.setattr(engine_home, "local_home_key", lambda: "")
    eng = FakeEngine(Config())
    eng._check_home()
    assert eng.home_client() is None and eng.home_info == {"state": "off"} and eng.events == []


def test_laptop_reloads_its_ai_when_home_stops_answering(monkeypatch):
    from voice_typer import engine_home, writer as writer_mod
    from voice_typer.config import Config

    cfg = Config()
    cfg.home_enabled, cfg.home_url, cfg.home_key, cfg.writer_preload = True, "hugo.tail1.ts.net", KEY, True
    monkeypatch.setattr(engine_home, "local_home_key", lambda: "")
    monkeypatch.setattr(writer_mod, "is_downloaded", lambda source: True)
    eng = FakeEngine(cfg)
    eng.writer = None
    loads = []
    eng.load_writer = lambda: loads.append(1)
    eng._home_result(False, "unreachable")
    assert loads == [1]                                          # ready for the next email, on this PC

def test_laptop_gets_the_home_graphics_memory(monkeypatch):
    from voice_typer import engine_home
    from voice_typer.config import Config

    cfg = Config()
    cfg.home_enabled, cfg.home_url, cfg.home_key = True, "hugo.tail1.ts.net", KEY
    monkeypatch.setattr(engine_home, "local_home_key", lambda: "")
    monkeypatch.setattr(home.HomeClient, "ping", lambda self: {"device": "cuda", "vram_used_mb": 8000,
                                                               "vram_total_mb": 8192})
    eng = FakeEngine(cfg)
    eng._check_home()
    assert eng.home_info["vram_used"] == 8000 and eng.home_info["vram_total"] == 8192


def test_connection_code_from_home_connections():
    key = "AbC-_" + "x" * 40
    assert home.parse_connection_code(f"  https://hugo.tail3001ff.ts.net/#key={key}\n") == \
        ("https://hugo.tail3001ff.ts.net", key)
    assert home.parse_connection_code(key) == ("", key)
    assert home.parse_connection_code("https://hugo.tail3001ff.ts.net/") == ("https://hugo.tail3001ff.ts.net", "")
    for bad in ("", "bonjour", "https://x.ts.net#key=court", "ftp://x#key=" + key, "#key=" + key):
        with pytest.raises(home.HomeError):
            home.parse_connection_code(bad)


def test_client_says_the_window_is_open(monkeypatch):
    sent = []
    monkeypatch.setattr(home, "_open", lambda req, timeout: sent.append(req) or Answer({"ok": True, "models": []}))
    home.HomeClient("hugo.tail1.ts.net", KEY).presence(True)
    assert sent[0].full_url == "https://hugo.tail1.ts.net/v1/presence"
    assert json.loads(sent[0].data) == {"active": True} and sent[0].get_header("X-app") == "voicetyper-pc"


def test_window_open_sends_presence_then_leaves():
    import threading

    from voice_typer.config import Config

    cfg = Config()
    cfg.home_enabled, cfg.home_url, cfg.home_key = True, "hugo.tail1.ts.net", KEY
    eng = FakeEngine(cfg)
    calls, got = [], threading.Event()

    class Client:
        def presence(self, active):
            calls.append(active)
            got.set()
            if active is None:
                raise home.HomeError("unreachable")

    eng.home_client = lambda: Client()
    eng.PRESENCE_EVERY = 0.05
    eng.set_window_open(True)
    assert got.wait(2)
    eng.set_window_open(True)                      # already open: nothing new
    eng.set_window_open(False)
    eng._presence_thread.join(2)
    import time
    time.sleep(0.1)
    # the loop's last « open » may land just after « closed » (Home Connections then forgets it after 45 s)
    assert calls[0] is True and calls.count(False) == 1 and not eng._presence_thread.is_alive()
    eng._send_presence(Client(), None)             # errors are swallowed
