"""Power sharing between PCs (voice_typer/remote.py): code format, server, client, device counting."""

import socket
import types

import numpy as np
import pytest

from voice_typer import remote


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeTranscriber:
    source = "small"
    device = "cuda"

    def transcribe(self, audio, language=None, hotwords=None):
        return f"final {audio.size} {language} {hotwords}"

    def preview(self, audio, language=None):
        return f"preview {audio.size}"


@pytest.fixture
def host(tmp_path):
    engine = types.SimpleNamespace(
        transcriber=FakeTranscriber(),
        config=types.SimpleNamespace(writing_model="qwen"),
        local_transcriber=lambda: engine.transcriber,
        rewrite_local=lambda text, instr, sig: f"{instr}:{text}:{sig}",
    )
    h = remote.Host(engine, _free_port(), "secret-key", remote.DeviceStats(tmp_path / "dev.json"),
                    bind="127.0.0.1",  # loopback: no firewall prompt
                    cert_file=tmp_path / "cert.pem", key_file=tmp_path / "key.pem")
    h.start()
    yield h
    h.stop()


FP = "ab" * 32


def _client(host, key="secret-key", cid="dev-1", name=None, fp=None):
    return remote.Client(f"127.0.0.1:{host.port}", key, cid, name, fingerprint=host.fingerprint if fp is None else fp)


def test_code_roundtrip():
    code = remote.make_code("100.64.1.2", 8765, "abc_DEF-123", FP)
    assert code.startswith("VT2-")
    assert remote.parse_code(" " + code[:10] + "\n" + code[10:]) == ("https://100.64.1.2:8765", "abc_DEF-123", FP)
    with pytest.raises(Exception):
        remote.parse_code("hello")
    with pytest.raises(ValueError):
        remote.parse_code(remote.make_code("1.2.3.4", 1, "k", "not-a-fingerprint"))


def test_old_unencrypted_code_refused():
    import base64
    import json
    old = "VT1-" + base64.urlsafe_b64encode(json.dumps({"a": "1.2.3.4:8765", "k": "x"}).encode()).decode()
    with pytest.raises(remote.OldCodeError):
        remote.parse_code(old)


def test_normalize_url():
    assert remote.normalize_url("192.168.1.5") == "https://192.168.1.5:8765"
    assert remote.normalize_url("http://pc:9000/") == "https://pc:9000"


def test_local_addresses_only():
    for ip in ("192.168.1.5", "10.0.0.2", "172.16.4.4", "127.0.0.1", "100.101.102.103", "::1",
               "fd7a:115c:a1e0::1", "fe80::1%12", "::ffff:192.168.1.9", "169.254.3.3"):
        assert remote.is_local_address(ip), ip
    for ip in ("8.8.8.8", "142.250.1.1", "2001:4860::8888", "::ffff:8.8.8.8", "garbage"):
        assert not remote.is_local_address(ip), ip


def test_internet_address_dropped(host):
    srv = host._httpd
    assert srv.verify_request(None, ("192.168.1.20", 5000))
    assert not srv.verify_request(None, ("8.8.8.8", 5000))
    srv.allow_internet = True
    assert srv.verify_request(None, ("8.8.8.8", 5000))


def test_certificate_is_persistent(tmp_path):
    a = remote.ensure_certificate(tmp_path / "c.pem", tmp_path / "k.pem")
    assert len(a) == 64 and a == remote.ensure_certificate(tmp_path / "c.pem", tmp_path / "k.pem")


def test_wrong_fingerprint_refused_before_sending_key(host):
    """A machine pretending to be the host (other certificate) never receives the key."""
    with pytest.raises(remote.RemoteError, match="bad_certificate"):
        _client(host, fp=FP).ping()
    assert host.stats.snapshot() == [] and not host._failed   # no request reached the host
    with pytest.raises(remote.RemoteError, match="no_fingerprint"):
        remote.Client(f"127.0.0.1:{host.port}", "secret-key", "dev").ping()


def test_plain_http_not_served(host):
    import urllib.request
    with pytest.raises(Exception):
        urllib.request.urlopen(f"http://127.0.0.1:{host.port}/api/ping", timeout=3).read()


def test_transcribe_rewrite_and_counting(host):
    c = _client(host, name="Bureau")
    info = c.ping()
    assert info["device"] == "cuda" and info["model"] == "small"
    audio = np.zeros(16000, dtype=np.float32)
    assert c.transcribe(audio, "fr", "Tailscale, Qwen") == "final 16000 fr Tailscale, Qwen"
    assert c.transcribe(audio, "fr", preview=True) == "preview 16000"
    assert c.rewrite("salut", "Courriel", "Hugo") == "Courriel:salut:Hugo"
    rows = host.stats.snapshot()
    assert len(rows) == 1 and rows[0]["name"] == "Bureau"
    assert rows[0]["dictations"] == 1 and rows[0]["rewrites"] == 1   # previews are not counted
    assert rows[0]["audio_s"] == 1.0
    _client(host, cid="dev-2", name="Portable").ping()
    assert host.stats.active_count() == 2


def test_wrong_key_refused(host):
    c = _client(host, key="nope", cid="dev-x")
    with pytest.raises(remote.RemoteError, match="bad_key"):
        c.ping()
    assert host.stats.snapshot() == []


def test_unreachable_raises_remote_error():
    c = remote.Client(f"127.0.0.1:{_free_port()}", "k", "dev", fingerprint=FP)
    with pytest.raises(remote.RemoteError):
        c.ping(timeout=1)


def test_brute_force_lockout(host, monkeypatch):
    monkeypatch.setattr(remote.time, "sleep", lambda s: None)
    for _ in range(10):
        assert not host.check_key("192.168.1.66", "guess")
    assert not host.check_key("192.168.1.66", "secret-key")   # even the right key: locked for a while
    assert host.check_key("192.168.1.67", "secret-key")       # other devices unaffected
