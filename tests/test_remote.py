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
                    bind="127.0.0.1")  # loopback: no firewall prompt
    h.start()
    yield h
    h.stop()


def test_code_roundtrip():
    code = remote.make_code("100.64.1.2", 8765, "abc_DEF-123")
    assert code.startswith("VT1-")
    assert remote.parse_code(" " + code[:10] + "\n" + code[10:]) == ("http://100.64.1.2:8765", "abc_DEF-123")
    with pytest.raises(Exception):
        remote.parse_code("hello")


def test_normalize_url():
    assert remote.normalize_url("192.168.1.5") == "http://192.168.1.5:8765"
    assert remote.normalize_url("http://pc:9000/") == "http://pc:9000"


def test_transcribe_rewrite_and_counting(host):
    c = remote.Client(f"127.0.0.1:{host.port}", "secret-key", "dev-1", "Bureau")
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
    remote.Client(f"127.0.0.1:{host.port}", "secret-key", "dev-2", "Portable").ping()
    assert host.stats.active_count() == 2


def test_wrong_key_refused(host):
    c = remote.Client(f"127.0.0.1:{host.port}", "nope", "dev-x")
    with pytest.raises(remote.RemoteError, match="bad_key"):
        c.ping()
    assert host.stats.snapshot() == []


def test_unreachable_raises_remote_error():
    c = remote.Client(f"127.0.0.1:{_free_port()}", "k", "dev")
    with pytest.raises(remote.RemoteError):
        c.ping(timeout=1)
