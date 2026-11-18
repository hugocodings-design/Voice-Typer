"""Automatic updates (voice_typer/updater.py): version compare, manifest checks, verified download."""

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from voice_typer import updater

PAYLOAD = b"MZ fake installer " * 50000
KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw,
                                                     serialization.PublicFormat.Raw)).decode()


def _sign(info, key=KEY):
    info = {k: v for k, v in info.items() if k != "signature"}
    info["signature"] = base64.b64encode(key.sign(updater.signed_bytes(info))).decode()
    return info


def _manifest(version="99.0.0", sha=None, url=None, sign=True):
    m = {"version": version, "url": url or updater.ALLOWED_PREFIX + "v99.0.0/VoiceTyperSetup-99.0.0.exe",
         "sha256": sha or hashlib.sha256(PAYLOAD).hexdigest(), "size": len(PAYLOAD), "notes_fr": "x"}
    return _sign(m) if sign else m


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
        updater.validate(_manifest(url="https://evil.example/setup.exe"), PUB)
    with pytest.raises(updater.UpdateError):
        updater.validate(_manifest(sha="1234"), PUB)
    assert updater.validate(_manifest(), PUB)["size"] == len(PAYLOAD)


def test_signature_required():
    with pytest.raises(updater.UpdateError, match="unsigned"):
        updater.validate(_manifest(sign=False), PUB)
    tampered = {**_manifest(), "sha256": "0" * 64}   # someone swaps the installer
    with pytest.raises(updater.UpdateError, match="bad signature"):
        updater.validate(tampered, PUB)
    other = _sign(_manifest(sign=False), Ed25519PrivateKey.generate())  # signed with another key
    with pytest.raises(updater.UpdateError, match="bad signature"):
        updater.validate(other, PUB)
    with pytest.raises(updater.UpdateError):
        updater.validate({**_manifest(), "signature": "not base64!"}, PUB)


def test_real_public_key_is_a_valid_ed25519_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from voice_typer.update_key import UPDATE_PUBLIC_KEY

    Ed25519PublicKey.from_public_bytes(base64.b64decode(UPDATE_PUBLIC_KEY))


def test_old_copies_still_accept_signed_manifest():
    """0.8.x only checks version / url / sha256 / size and ignores unknown fields."""
    m = _manifest()
    assert {"version", "url", "sha256", "size"} <= m.keys()
    assert isinstance(m["size"], int) and m["url"].startswith(updater.ALLOWED_PREFIX)


def test_check(server):
    base, routes = server
    routes["/latest.json"] = json.dumps(_manifest()).encode()
    assert updater.check(manifest_url=base + "/latest.json", public_key=PUB)["version"] == "99.0.0"
    routes["/latest.json"] = json.dumps(_manifest(version="0.0.1")).encode()
    assert updater.check(manifest_url=base + "/latest.json", public_key=PUB) is None
    with pytest.raises(updater.UpdateError):
        updater.check(manifest_url=base + "/missing.json", public_key=PUB)


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


def test_required_flag_is_signed_and_detected():
    key = Ed25519PrivateKey.generate()
    pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,
                                                         serialization.PublicFormat.Raw)).decode()

    def signed(info):
        return {**info, "signature": base64.b64encode(key.sign(updater.signed_bytes(info))).decode()}

    base = {"version": "9.9.9", "url": updater.ALLOWED_PREFIX + "v9.9.9/VoiceTyperSetup-9.9.9.exe",
            "sha256": "a" * 64, "size": 1}
    required = signed({**base, "required": True})
    assert updater.is_required(updater.validate(required, pub))
    with pytest.raises(updater.UpdateError):          # the flag cannot be removed without the key…
        updater.validate({**required, "required": False}, pub)
    normal = signed(base)
    assert not updater.is_required(updater.validate(normal, pub))
    with pytest.raises(updater.UpdateError):          # …nor added to a normal update
        updater.validate({**normal, "required": True}, pub)
    assert not updater.is_required(None)
