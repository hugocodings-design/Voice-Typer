"""« PC à la maison »: the work PC is only a client (voice_typer/home.py); home_server runs at home."""

import json
import threading
import zlib

import numpy as np
import pytest

from home_server import server
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


def test_key_lockout():
    now = [0.0]
    guard = server.Guard(KEY, clock=lambda: now[0])
    assert guard.check(f"Bearer {KEY}") == "ok"
    for _ in range(server.LOCK_AFTER):
        assert guard.check("Bearer wrong") == "bad_key"
    assert guard.check(f"Bearer {KEY}") == "locked"          # even the right key, for a minute
    now[0] += server.LOCK_WINDOW + 1
    assert guard.check(f"Bearer {KEY}") == "ok"


def test_key_is_created_once(tmp_path):
    key = server.load_or_create_key(tmp_path)
    assert len(key) >= 40 and server.load_or_create_key(tmp_path) == key


class FakeT:
    device = "cuda"

    def __init__(self, source):
        self.source, self.seen = source, []

    def transcribe(self, audio, language, hotwords, mode="accurate"):
        self.seen.append((audio.size, language, hotwords, mode))
        return f"Bonjour ({self.source})."


class FakeW:
    device = "cuda"
    last_timings = {"rewrite": 0.4}

    def __init__(self, source):
        self.source = source

    def rewrite(self, text, *a, **k):
        return text.upper() + "\nHugo"


def fake_models(ready=True):
    m = server.Models(builders={"whisper": FakeT, "writer": FakeW},
                      defaults={"whisper": "large-v3-turbo", "writer": "qwen-3b"},
                      allowed={"whisper": {"small", "large-v3-turbo"}, "writer": {"qwen-3b", "qwen-1.5b"}},
                      log=lambda *_: None)
    if ready:
        for kind, src in (("whisper", "large-v3-turbo"), ("whisper", "small"), ("writer", "qwen-3b")):
            m.loading[kind] = src
            m._load(kind, src)
    return m


def _h(**extra):
    return {"Authorization": f"Bearer {KEY}", **extra}


def _opts(**kw):
    return json.dumps({"language": "fr", "mode": "auto", "sample_rate": 16000, **kw})


def test_api_without_sockets():
    m, g = fake_models(), server.Guard(KEY)
    assert server.handle(m, g, "GET", "/v1/ping", {}, b"")[0] == 401
    status, out = server.handle(m, g, "GET", "/v1/ping", _h(), b"", "9.9")
    assert status == 200 and out["device"] == "cuda" and out["version"] == "9.9"
    body = home.encode_audio(np.zeros(16000, dtype=np.float32))
    status, out = server.handle(m, g, "POST", "/v1/transcribe",
                                _h(**{"X-VT-Options": _opts(hotwords="Gagnon", model="small")}), body)
    assert status == 200 and out == {"text": "Bonjour (small).", "seconds": out["seconds"], "model": "small"}
    assert m.objs["whisper"].seen == [(16000, "fr", "Gagnon", "auto")]
    bad = json.dumps({"language": "de"})
    assert server.handle(m, g, "POST", "/v1/transcribe", _h(**{"X-VT-Options": bad}), body)[0] == 400
    too_long = home.encode_audio(np.zeros(16000 * (server.MAX_AUDIO_SECONDS + 1), dtype=np.float32))
    assert server.handle(m, g, "POST", "/v1/transcribe", _h(), too_long)[0] == 413
    req = json.dumps({"text": "salut", "writing_model": "qwen-3b"}).encode()
    status, out = server.handle(m, g, "POST", "/v1/rewrite", _h(), req)
    assert status == 200 and out == {"text": "SALUT\nHugo", "timings": {"rewrite": 0.4}, "model": "qwen-3b",
                                    "device": "cuda"}
    assert server.handle(m, g, "POST", "/v1/rewrite", _h(), b"not json")[0] == 400
    assert server.handle(m, g, "GET", "/etc/passwd", _h(), b"")[0] == 404


def test_the_model_selected_on_the_other_pc_is_loaded():
    m, g = fake_models(), server.Guard(KEY)
    body = home.encode_audio(np.zeros(1600, dtype=np.float32))
    # a model not loaded yet: "loading" (the other PC does this one), then it is used
    status, _ = server.handle(m, g, "POST", "/v1/transcribe", _h(**{"X-VT-Options": _opts(model="large-v3-turbo")}),
                              body)
    for t in list(threading.enumerate()):
        if t.name != "MainThread" and t.daemon:
            t.join(timeout=2)
    status, out = server.handle(m, g, "POST", "/v1/transcribe",
                                _h(**{"X-VT-Options": _opts(model="large-v3-turbo")}), body)
    assert status == 200 and out["model"] == "large-v3-turbo"


def test_unknown_models_use_this_pcs_own_choice():
    m = fake_models(ready=False)
    assert m.choose("whisper", r"C:\Users\x\my-model") == "large-v3-turbo"   # a folder on the other PC
    assert m.choose("whisper", "evil/repo") == "large-v3-turbo"               # never downloads anything else
    assert m.choose("whisper", "small") == "small"
    assert m.choose("writer", None) == "qwen-3b"
    m.failed["small"] = "broken"
    assert m.choose("whisper", "small") == "large-v3-turbo"


def test_answers_loading_until_models_are_ready():
    m = fake_models(ready=False)
    m._builders = {"whisper": lambda s: (_ for _ in ()).throw(RuntimeError("slow")), "writer": FakeW}
    body = home.encode_audio(np.zeros(1600, dtype=np.float32))
    assert server.handle(m, server.Guard(KEY), "POST", "/v1/transcribe", _h(), body)[0] == 503


def test_client_and_server_round_trip():
    """Real HTTP on 127.0.0.1 (Funnel would add HTTPS in front)."""
    m = fake_models()
    srv = server.make_server(m, KEY, 0)
    assert srv.server_address[0] == "127.0.0.1"               # never reachable from the network directly
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        client = home.HomeClient(url, KEY)
        assert client.ping()["writer"] == "qwen-3b"
        assert client.transcribe(np.zeros(8000, dtype=np.float32), 16000, "en", None, "fast",
                                 "small") == "Bonjour (small)."
        text, timings = client.rewrite("hi", "", "Hugo", True, False, False, "", "en", "qwen-3b")
        assert text == "HI\nHugo" and timings == {"rewrite": 0.4}
        with pytest.raises(home.HomeError, match="bad_key"):
            home.HomeClient(url, "wrong").ping()
    finally:
        srv.shutdown()
        srv.server_close()


def test_work_package_still_has_no_server_code():
    """home_server lives outside voice_typer: the installed app (PyInstaller bundles voice_typer) has none."""
    from pathlib import Path

    import voice_typer
    src = Path(voice_typer.__file__).parent
    assert not (src / "home_server").exists()
    code = "".join(p.read_text(encoding="utf-8") for p in src.rglob("*.py"))
    assert "import home_server" not in code and "from home_server" not in code


def test_tray_texts():
    from home_server import tray_app

    lines = tray_app.status_lines({"whisper": ("small", "cuda", None),
                                   "writer": ("jncraton/Qwen2.5-3B-Instruct-ct2-int8", "cpu", None)})
    assert lines == ["Whisper : small — carte graphique", "IA d'écriture : Qwen2.5-3B-Instruct — PROCESSEUR (lent)"]
    assert "chargement de large-v3" in tray_app.status_lines({"whisper": ("", "", "large-v3")})[0]
    assert tray_app.load_message("writer", "q", "cuda", "") is None
    assert "processeur" in tray_app.load_message("writer", "q", "cpu", "")
    assert "impossible" in tray_app.load_message("whisper", "x", "", "boom")
    assert tray_app.autostart_command().endswith('run_home.pyw"') and "pythonw" in tray_app.autostart_command()


def test_load_events_reach_the_tray():
    m = fake_models(ready=False)
    seen = []
    m.on_event = lambda *a: seen.append(a)
    m.loading["writer"] = "qwen-3b"
    m._load("writer", "qwen-3b")
    assert seen == [("writer", "qwen-3b", "cuda", "")]
    assert m.status()["writer"] == ("qwen-3b", "cuda", None, False)


def test_journal_never_holds_dictations(tmp_path):
    from home_server import tray_app

    log = tray_app.setup_log(tmp_path)
    m = fake_models()
    m.log = log.info
    body = home.encode_audio(np.zeros(1600, dtype=np.float32))
    server.handle(m, server.Guard(KEY), "POST", "/v1/transcribe", _h(**{"X-VT-Options": _opts(model="small")}), body)
    for h in log.handlers:
        h.flush()
    text = (tmp_path / "home.log").read_text(encoding="utf-8")
    assert "dictée" in text and "Bonjour" not in text


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


def test_graphics_memory_reading():
    from home_server import gpu_memory

    assert gpu_memory.parse("7890, 8192\n") == (7890, 8192)
    assert gpu_memory.parse("garbage") is None
    assert gpu_memory.is_full(7700, 8192) and not gpu_memory.is_full(5000, 8192)
    assert gpu_memory.describe(8090, 8192) == "Mémoire graphique : 7,9 / 8,0 Go — PLEINE (lent)"
    assert gpu_memory.describe(5222, 8192) == "Mémoire graphique : 5,1 / 8,0 Go"
    calls, now = [], [0.0]
    mon = gpu_memory.Monitor(reader=lambda: calls.append(1) or (1, 2), every=10, clock=lambda: now[0])
    mon.get(), mon.get()
    now[0] = 11
    mon.get()
    assert len(calls) == 2                                       # read at most every 10 s


def test_ping_reports_graphics_memory_and_tray_warns():
    from home_server import tray_app

    m = fake_models()
    m.vram.reader, m.vram._at = (lambda: (8000, 8192)), -1e9
    status, out = server.handle(m, server.Guard(KEY), "GET", "/v1/ping", _h(), b"")
    assert out["vram_used_mb"] == 8000 and out["vram_total_mb"] == 8192
    lines = tray_app.health_lines((8000, 8192), (5.5, 6.2), "cuda")
    assert "PLEINE" in lines[0] and "Dernière dictée lente : 5,5 s pour 6,2 s" in lines[1]
    assert tray_app.health_lines((3000, 8192), (0.4, 6.2), "cuda") == ["Mémoire graphique : 2,9 / 8,0 Go"]
    assert "Large v3 Turbo compact" in tray_app.full_message((8000, 8192))


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


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _join_loaders():
    for t in list(threading.enumerate()):
        if t.name != "MainThread" and t.daemon and t.name != "home-idle":
            t.join(timeout=2)


def test_home_frees_the_graphics_card_when_unused():
    clock = Clock()
    m = server.Models(builders={"whisper": FakeT, "writer": FakeW},
                      defaults={"whisper": "large-v3-turbo", "writer": "qwen-3b"},
                      allowed={"whisper": {"small", "large-v3-turbo"}, "writer": {"qwen-3b"}},
                      log=lambda *_: None, idle_s=300, clock=clock)
    m.last_device = {"whisper": "cuda", "writer": "cuda"}
    g = server.Guard(KEY)
    # starts asleep: nothing on the card, yet the laptop is told the models run on the graphics card
    m.asleep = {"whisper": "large-v3-turbo", "writer": "qwen-3b"}
    status, out = server.handle(m, g, "GET", "/v1/ping", _h(), b"")
    assert out["asleep"] == ["whisper", "writer"] and out["device"] == "cuda" and out["writer_device"] == "cuda"
    assert out["whisper"] == "large-v3-turbo" and m.objs["whisper"] is None and m.objs["writer"] is None
    from home_server import tray_app

    assert "en veille" in tray_app.status_lines(m.status())[0]
    # a dictation wakes BOTH models (an e-mail needs the writing AI right after) and is answered, not refused
    body = home.encode_audio(np.zeros(1600, dtype=np.float32))
    status, out = server.handle(m, g, "POST", "/v1/transcribe", _h(**{"X-VT-Options": _opts()}), body)
    assert status == 200 and out["model"] == "large-v3-turbo"
    _join_loaders()
    assert m.objs["writer"] is not None and m.asleep == {}
    # pings every minute do not count as use; 5 min after the last dictation the card is freed
    clock.now += 299
    server.handle(m, g, "GET", "/v1/ping", _h(), b"")
    assert m.sleep_if_idle() is False
    clock.now += 2
    assert m.sleep_if_idle() is True
    assert m.objs["whisper"] is None and m.objs["writer"] is None
    assert m.asleep == {"whisper": "large-v3-turbo", "writer": "qwen-3b"}
    assert m.sleep_if_idle() is False          # nothing left to free
    # an e-mail wakes them again
    req = json.dumps({"text": "salut"}).encode()
    status, out = server.handle(m, g, "POST", "/v1/rewrite", _h(), req)
    assert status == 200 and out["text"] == "SALUT\nHugo"
    _join_loaders()
    assert m.objs["whisper"] is not None


def test_home_never_sleeps_during_a_dictation_or_with_idle_off():
    clock = Clock()
    m = fake_models()
    m.clock, m.idle_s = clock, 300
    clock.now += 1000
    with m.gpu:                                # a dictation is running on the card
        assert m.sleep_if_idle() is False
    m.idle_s = 0
    assert m.sleep_if_idle() is False
    assert m.objs["whisper"] is not None


def test_home_starts_asleep():
    m = fake_models(ready=False)
    m.idle_s = 300
    started = []
    real_thread = server.threading.Thread
    server.threading.Thread = lambda *a, **k: started.append(k.get("name")) or real_thread(target=lambda: None)
    try:
        m.start()
    finally:
        server.threading.Thread = real_thread
    assert m.asleep == {"whisper": "large-v3-turbo", "writer": "qwen-3b"} and started == ["home-idle"]
    assert m.objs["whisper"] is None and not any(m.loading.values())
