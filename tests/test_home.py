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
    assert status == 200 and out == {"text": "SALUT\nHugo", "timings": {"rewrite": 0.4}, "model": "qwen-3b"}
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
