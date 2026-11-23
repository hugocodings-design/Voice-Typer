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


class FakeModels(server.Models):
    def __init__(self):
        super().__init__()
        self.transcriber = type("T", (), {"device": "cuda"})()
        self.writer = object()
        self.whisper_name, self.writer_name = "large-v3-turbo", "Qwen"
        self.seen = []

    def transcribe(self, audio, language, hotwords, mode):
        self.seen.append((audio.size, language, hotwords, mode))
        return "Bonjour."

    def rewrite(self, req):
        return req["text"].upper() + "\nHugo", {"rewrite": 0.4}


def _h(**extra):
    return {"Authorization": f"Bearer {KEY}", **extra}


def test_api_without_sockets():
    m, g = FakeModels(), server.Guard(KEY)
    assert server.handle(m, g, "GET", "/v1/ping", {}, b"")[0] == 401
    status, out = server.handle(m, g, "GET", "/v1/ping", _h(), b"", "9.9")
    assert status == 200 and out["device"] == "cuda" and out["version"] == "9.9"
    body = home.encode_audio(np.zeros(16000, dtype=np.float32))
    opts = json.dumps({"language": "fr", "hotwords": "Gagnon", "mode": "auto", "sample_rate": 16000})
    status, out = server.handle(m, g, "POST", "/v1/transcribe", _h(**{"X-VT-Options": opts}), body)
    assert status == 200 and out["text"] == "Bonjour." and m.seen == [(16000, "fr", "Gagnon", "auto")]
    bad = json.dumps({"language": "de"})
    assert server.handle(m, g, "POST", "/v1/transcribe", _h(**{"X-VT-Options": bad}), body)[0] == 400
    too_long = home.encode_audio(np.zeros(16000 * (server.MAX_AUDIO_SECONDS + 1), dtype=np.float32))
    assert server.handle(m, g, "POST", "/v1/transcribe", _h(), too_long)[0] == 413
    status, out = server.handle(m, g, "POST", "/v1/rewrite", _h(), json.dumps({"text": "salut"}).encode())
    assert status == 200 and out == {"text": "SALUT\nHugo", "timings": {"rewrite": 0.4}}
    assert server.handle(m, g, "POST", "/v1/rewrite", _h(), b"not json")[0] == 400
    assert server.handle(m, g, "GET", "/etc/passwd", _h(), b"")[0] == 404


def test_answers_loading_until_models_are_ready():
    m = server.Models()
    body = home.encode_audio(np.zeros(1600, dtype=np.float32))
    assert server.handle(m, server.Guard(KEY), "POST", "/v1/transcribe", _h(), body)[0] == 503


def test_client_and_server_round_trip():
    """Real HTTP on 127.0.0.1 (Funnel would add HTTPS in front)."""
    m = FakeModels()
    srv = server.make_server(m, KEY, 0)
    assert srv.server_address[0] == "127.0.0.1"               # never reachable from the network directly
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        client = home.HomeClient(url, KEY)
        assert client.ping()["whisper"] == "large-v3-turbo"
        assert client.transcribe(np.zeros(8000, dtype=np.float32), 16000, "en", None, "fast") == "Bonjour."
        text, timings = client.rewrite("hi", "", "Hugo", True, False, False, "", "en")
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
