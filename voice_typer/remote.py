"""Share one PC's AI power with other devices ("home server").

The *host* (e.g. the powerful PC at home, with its NVIDIA card) runs a small HTTPS server. Other
copies of Voice Typer (*clients*, e.g. the PC at work) send it the recorded audio and get the
text back, and can also ask it to do the AI writing. Everything still runs on your own machines:
nothing goes through a cloud service.

    POST /api/transcribe   body: 16 kHz mono int16 PCM; headers X-Language, X-Hotwords, X-Pass
    POST /api/rewrite      JSON {"text", "instructions", "signature"}
    GET  /api/ping         what the host runs (model, GPU…)

Security:
* Everything is encrypted with TLS. The host makes its own self-signed certificate on first use;
  its SHA-256 fingerprint is part of the connection code, and the client checks it on every
  connection (certificate pinning: no certificate authority needed, no man-in-the-middle).
* Every request carries `Authorization: Bearer <access key>` (also in the code), compared in
  constant time; 10 wrong keys in 5 minutes from one address and it is ignored for a while.
* By default the host only accepts private / local addresses (home network, Tailscale 100.x):
  connections from the public Internet are dropped before any TLS exchange.

Devices introduce themselves with X-Client-Id / X-Client-Name, which is how the host counts its users.

To reach the host from outside the home network, the simplest safe way is Tailscale (a free
private network between your own devices): no router setup, traffic is encrypted.
"""

import base64
import datetime as dt
import hashlib
import hmac
import http.client
import ipaddress
import json
import secrets
import socket
import ssl
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from voice_typer import __version__
from voice_typer.config import SETTINGS_DIR

DEFAULT_PORT = 8765
STATS_FILE = SETTINGS_DIR / "server_devices.json"
ACTIVE_WINDOW = 10 * 60          # a device counts as "connected now" if seen in the last 10 minutes
MAX_BODY = 40 * 1024 * 1024      # ~20 min of audio
SAMPLE_RATE = 16_000
CODE_PREFIX = "VT2-"            # VT1- codes (plain HTTP, before 0.9.0) are refused: re-pair
CERT_FILE = SETTINGS_DIR / "host_certificate.pem"
CERT_KEY_FILE = SETTINGS_DIR / "host_certificate_key.pem"
_CGNAT = ipaddress.ip_network("100.64.0.0/10")   # Tailscale addresses


class OldCodeError(ValueError):
    """A connection code from a version before encryption (VT1-)."""


def new_key() -> str:
    return secrets.token_urlsafe(18)


# ---- connection code: address + key in one string to copy to the other device -------------------
def make_code(address: str, port: int, key: str, fingerprint: str) -> str:
    raw = json.dumps({"a": f"{address}:{port}", "k": key, "f": fingerprint}, separators=(",", ":")).encode()
    return CODE_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_code(code: str) -> tuple[str, str, str]:
    """Returns (base_url, key, certificate fingerprint). Raises ValueError if the code is not
    valid, OldCodeError for a code made before encryption."""
    code = "".join(code.split())
    if code.upper().startswith("VT1-"):
        raise OldCodeError("old code")
    if not code.upper().startswith(CODE_PREFIX):
        raise ValueError("bad prefix")
    body = code[len(CODE_PREFIX):]
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    fp = str(data["f"]).lower()
    if len(fp) != 64 or any(c not in "0123456789abcdef" for c in fp):
        raise ValueError("bad fingerprint")
    return normalize_url(data["a"]), str(data["k"]), fp


def normalize_url(address: str) -> str:
    address = address.strip().rstrip("/")
    if not address:
        return ""
    address = address.replace("http://", "https://", 1)   # always encrypted
    if "://" not in address:
        address = "https://" + address
    parts = urllib.parse.urlsplit(address)
    if parts.port is None:
        address = f"{parts.scheme}://{parts.hostname}:{DEFAULT_PORT}"
    return address


def local_addresses() -> list[tuple[str, str]]:
    """[(kind, ip)] for this PC: kind is "tailscale" (100.64.0.0/10) or "lan"."""
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:  # the address used for outgoing traffic (no packet is actually sent)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    out = []
    for ip in sorted(ips):
        addr = ipaddress.ip_address(ip)
        if addr.is_loopback or addr.is_link_local:
            continue
        if addr in cgnat:
            out.insert(0, ("tailscale", ip))
        elif addr.is_private:
            out.append(("lan", ip))
    return out


# ================================================================================ host side
def ensure_certificate(cert_file: Path = CERT_FILE, key_file: Path = CERT_KEY_FILE) -> str:
    """Creates the host's self-signed TLS certificate on first use. Returns its SHA-256 fingerprint."""
    if not (cert_file.exists() and key_file.exists()):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Voice Typer host")])
        now = dt.datetime.now(dt.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
                .sign(key, hashes.SHA256()))
        cert_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return fingerprint_of(ssl.PEM_cert_to_DER_cert(cert_file.read_text(encoding="ascii")))


def fingerprint_of(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


def is_local_address(ip: str) -> bool:
    """Home network, loopback, link-local or Tailscale (100.64.0.0/10)."""
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_private or addr.is_loopback or addr.is_link_local or (
        isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT)


class _TLSServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_internet = False
    ssl_context: ssl.SSLContext

    def verify_request(self, request, client_address) -> bool:
        return self.allow_internet or is_local_address(client_address[0])

    def finish_request(self, request, client_address) -> None:
        # TLS handshake here, in the connection's own thread (a slow client can't block the others)
        try:
            request.settimeout(30)
            tls = self.ssl_context.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return
        try:
            super().finish_request(tls, client_address)
        finally:
            try:
                tls.close()
            except OSError:
                pass


class DeviceStats:
    """Which devices use the host, persisted so the count survives restarts."""

    def __init__(self, path=STATS_FILE):
        self.path = path
        self.lock = threading.Lock()
        try:
            self.devices: dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.devices = {}
        self._dirty_since = 0.0

    def record(self, client_id: str, name: str, ip: str, kind: str, audio_s: float = 0.0) -> None:
        now = time.time()
        with self.lock:
            d = self.devices.setdefault(client_id, {"first_seen": now, "dictations": 0, "rewrites": 0,
                                                    "audio_s": 0.0})
            d.update(name=name[:60] or "?", ip=ip, last_seen=now)
            if kind == "transcribe":
                d["dictations"] += 1
                d["audio_s"] = round(d.get("audio_s", 0.0) + audio_s, 1)
            elif kind == "rewrite":
                d["rewrites"] += 1
            self._save()

    def touch(self, client_id: str, name: str, ip: str) -> None:
        with self.lock:
            d = self.devices.setdefault(client_id, {"first_seen": time.time(), "dictations": 0,
                                                    "rewrites": 0, "audio_s": 0.0})
            d.update(name=name[:60] or "?", ip=ip, last_seen=time.time())
            self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.devices, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def snapshot(self) -> list[dict]:
        with self.lock:
            rows = [{"id": k, **v} for k, v in self.devices.items()]
        return sorted(rows, key=lambda r: r.get("last_seen", 0), reverse=True)

    def active_count(self, window: float = ACTIVE_WINDOW) -> int:
        cutoff = time.time() - window
        with self.lock:
            return sum(1 for d in self.devices.values() if d.get("last_seen", 0) >= cutoff)

    def forget(self, client_id: str | None = None) -> None:
        with self.lock:
            if client_id is None:
                self.devices.clear()
            else:
                self.devices.pop(client_id, None)
            self._save()


class Host:
    """HTTP server sharing this PC's speech model and writing AI. Owned by the Engine."""

    def __init__(self, engine, port: int, key: str, stats: DeviceStats | None = None, bind: str = "0.0.0.0",
                 allow_internet: bool = False, cert_file: Path = CERT_FILE, key_file: Path = CERT_KEY_FILE):
        self.engine = engine
        self.bind = bind
        self.allow_internet = allow_internet
        self.cert_file, self.key_file = cert_file, key_file
        self.fingerprint = ensure_certificate(cert_file, key_file)
        self.port = port
        self.key = key
        self.stats = stats or DeviceStats()
        self.busy = 0                       # requests being processed right now
        self._model_lock = threading.Lock()  # one transcription at a time on the GPU
        self._httpd: ThreadingHTTPServer | None = None
        self._failed: dict[str, list[float]] = {}  # ip -> recent wrong-key attempts

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def start(self) -> None:
        if self._httpd:
            return
        host = self

        class Handler(_Handler):
            server_owner = host

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(self.cert_file, self.key_file)
        self._httpd = _TLSServer((self.bind, self.port), Handler)
        self._httpd.ssl_context = ctx
        self._httpd.allow_internet = self.allow_internet
        threading.Thread(target=self._httpd.serve_forever, daemon=True, name="vt-host").start()

    def stop(self) -> None:
        if self._httpd:
            httpd, self._httpd = self._httpd, None
            threading.Thread(target=lambda: (httpd.shutdown(), httpd.server_close()), daemon=True).start()

    # -- auth / brute-force protection
    def check_key(self, ip: str, given: str) -> bool:
        now = time.time()
        recent = [t for t in self._failed.get(ip, []) if now - t < 300]
        if len(recent) >= 10:   # 10 wrong keys in 5 min: ignore this address for a while
            self._failed[ip] = recent
            return False
        if given and hmac.compare_digest(given.encode(), self.key.encode()):
            return True
        recent.append(now)
        self._failed[ip] = recent
        time.sleep(0.5)
        return False

    # -- work
    def info(self) -> dict:
        tr = self.engine.transcriber
        return {"app": "voice-typer", "version": __version__, "name": socket.gethostname(),
                "model": getattr(tr, "source", None), "device": getattr(tr, "device", None),
                "writer": self.engine.config.writing_model}

    def transcribe(self, audio: np.ndarray, language: str | None, hotwords: str | None, fast: bool) -> str:
        tr = self.engine.local_transcriber()
        if tr is None:
            raise RuntimeError("no speech model loaded on the host")
        with self._model_lock:
            return tr.preview(audio, language) if fast else tr.transcribe(audio, language, hotwords)

    def rewrite(self, text: str, instructions: str, signature: str) -> str:
        return self.engine.rewrite_local(text, instructions, signature)


class _Handler(BaseHTTPRequestHandler):
    server_owner: Host
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # quiet (pythonw has no console)
        pass

    def _send(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> tuple[str, str] | None:
        host = self.server_owner
        auth = self.headers.get("Authorization", "")
        given = auth[7:] if auth.startswith("Bearer ") else ""
        if not host.check_key(self.client_address[0], given):
            self._send(401, {"error": "bad_key"})
            return None
        cid = (self.headers.get("X-Client-Id") or self.client_address[0])[:64]
        name = urllib.parse.unquote(self.headers.get("X-Client-Name") or "")
        return cid, name

    def _body(self) -> bytes | None:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            self._send(413, {"error": "too_large"})
            return None
        return self.rfile.read(n) if n else b""

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/api/ping":
            self._send(404, {"error": "not_found"})
            return
        who = self._auth()
        if who is None:
            return
        self.server_owner.stats.touch(who[0], who[1], self.client_address[0])
        self._send(200, self.server_owner.info())

    def do_POST(self) -> None:  # noqa: N802
        host = self.server_owner
        if self.path not in ("/api/transcribe", "/api/rewrite"):
            self._send(404, {"error": "not_found"})
            return
        who = self._auth()
        if who is None:
            return
        body = self._body()
        if body is None:
            return
        host.busy += 1
        try:
            ip = self.client_address[0]
            if self.path == "/api/transcribe":
                audio = np.frombuffer(body[: len(body) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0
                fast = self.headers.get("X-Pass") == "preview"
                text = host.transcribe(audio, self.headers.get("X-Language") or None,
                                       urllib.parse.unquote(self.headers.get("X-Hotwords") or "") or None, fast)
                if not fast:  # live previews are not counted as dictations
                    host.stats.record(who[0], who[1], ip, "transcribe", audio.size / SAMPLE_RATE)
                else:
                    host.stats.touch(who[0], who[1], ip)
            else:
                data = json.loads(body or b"{}")
                text = host.rewrite(str(data.get("text", "")), str(data.get("instructions", "")),
                                    str(data.get("signature", "")))
                host.stats.record(who[0], who[1], ip, "rewrite")
            self._send(200, {"text": text})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
        finally:
            host.busy -= 1


# ================================================================================ client side
class RemoteError(Exception):
    """The host could not be reached or refused the request (caller falls back to this PC)."""


class Client:
    def __init__(self, url: str, key: str, client_id: str, name: str | None = None, fingerprint: str = ""):
        self.url = normalize_url(url)
        parts = urllib.parse.urlsplit(self.url)
        self.host, self.port = parts.hostname or "", parts.port or DEFAULT_PORT
        self.key = key
        self.fingerprint = (fingerprint or "").lower()
        self.client_id = client_id
        self.name = name or socket.gethostname()
        # The certificate is self-signed: no CA check, the pinned fingerprint is checked instead.
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE
        self._ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    def _request(self, path: str, body: bytes | None = None, headers: dict | None = None,
                 timeout: float = 60) -> dict:
        if not self.fingerprint:
            raise RemoteError("no_fingerprint")   # paired before 0.9.0: needs the new code
        conn = http.client.HTTPSConnection(self.host, self.port, timeout=timeout, context=self._ctx)
        try:
            try:
                conn.connect()
            except (OSError, ssl.SSLError) as exc:  # unreachable, timeout, not TLS
                raise RemoteError(str(exc)) from exc
            der = conn.sock.getpeercert(binary_form=True) or b""
            # checked BEFORE anything (the access key, the audio) is sent
            if not hmac.compare_digest(fingerprint_of(der), self.fingerprint):
                raise RemoteError("bad_certificate")
            h = {"Authorization": f"Bearer {self.key}", "X-Client-Id": self.client_id,
                 "X-Client-Name": urllib.parse.quote(self.name), **(headers or {})}
            try:
                conn.request("POST" if body is not None else "GET", path, body=body, headers=h)
                resp = conn.getresponse()
                raw = resp.read()
            except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
                raise RemoteError(str(exc)) from exc
            try:
                data = json.loads(raw)
            except ValueError as exc:
                raise RemoteError("bad response") from exc
            if resp.status != 200:
                raise RemoteError(str(data.get("error", resp.status)) if isinstance(data, dict) else str(resp.status))
            return data
        finally:
            conn.close()

    def ping(self, timeout: float = 4) -> dict:
        return self._request("/api/ping", timeout=timeout)

    def transcribe(self, audio: np.ndarray, language: str | None, hotwords: str | None = None,
                   preview: bool = False) -> str:
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        headers = {"Content-Type": "application/octet-stream", "X-Pass": "preview" if preview else "final"}
        if language:
            headers["X-Language"] = language
        if hotwords:
            headers["X-Hotwords"] = urllib.parse.quote(hotwords)
        # generous timeout: long dictations on the host's first use (model warm-up)
        timeout = 10 if preview else 20 + audio.size / SAMPLE_RATE
        return self._request("/api/transcribe", pcm, headers, timeout)["text"]

    def rewrite(self, text: str, instructions: str, signature: str) -> str:
        body = json.dumps({"text": text, "instructions": instructions, "signature": signature}).encode()
        return self._request("/api/rewrite", body, {"Content-Type": "application/json"}, 120)["text"]
