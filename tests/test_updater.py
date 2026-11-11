"""Automatic updates (voice_typer/updater.py): version compare, manifest checks, verified download."""

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from voice_typer import updater

PAYLOAD = b"MZ fake installer " * 50000


def _manifest(version="99.0.0", sha=None, url=None):
    return {"version": version, "url": url or updater.ALLOWED_PREFIX + "v99.0.0/VoiceTyperSetup-99.0.0.exe",
            "sha256": sha or hashlib.sha256(PAYLOAD).hexdigest(), "size": len(PAYLOAD), "notes_fr": "x"}


@pytest.fixture
def server():
    routes = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            body = routes.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", routes
    httpd.shutdown()


def test_versions():
    assert updater.parse_version("v0.10.2") == (0, 10, 2)
    assert updater.is_newer("0.10.0", "0.9.9")
    assert not updater.is_newer("0.7.0", "0.7.0")
    assert not updater.is_newer("0.6.9", "0.7.0")


def test_validate_rejects_foreign_url_and_bad_hash():
    with pytest.raises(updater.UpdateError):
        updater.validate(_manifest(url="https://evil.example/setup.exe"))
    with pytest.raises(updater.UpdateError):
        updater.validate(_manifest(sha="1234"))
    assert updater.validate(_manifest())["size"] == len(PAYLOAD)


def test_check(server):
    base, routes = server
    routes["/latest.json"] = json.dumps(_manifest()).encode()
    assert updater.check(manifest_url=base + "/latest.json")["version"] == "99.0.0"
    routes["/latest.json"] = json.dumps(_manifest(version="0.0.1")).encode()
    assert updater.check(manifest_url=base + "/latest.json") is None
    with pytest.raises(updater.UpdateError):
        updater.check(manifest_url=base + "/missing.json")


def test_download_verifies_hash(server, tmp_path, monkeypatch):
    base, routes = server
    monkeypatch.setattr(updater, "DOWNLOAD_DIR", tmp_path)
    routes["/setup.exe"] = PAYLOAD
    seen = []
    path = updater.download({**_manifest(), "url": base + "/setup.exe"}, lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == PAYLOAD and seen[-1] == (len(PAYLOAD), len(PAYLOAD))
    path.unlink()
    with pytest.raises(updater.UpdateError, match="checksum"):
        updater.download({**_manifest(sha="0" * 64), "url": base + "/setup.exe"})
    assert list(tmp_path.iterdir()) == []   # nothing damaged left behind
