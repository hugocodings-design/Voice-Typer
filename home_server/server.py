"""Voice Typer Home — runs on YOUR home PC (NVIDIA card) and does the heavy work for your other PCs.

It is deliberately NOT part of the `voice_typer` package: the Voice Typer installed at work contains no server
code at all (IT requirement, tests/test_no_network_server.py). Start it from the project folder with
"Start Voice Typer Home.bat" (or `python -m home_server`).

Security:
- listens on 127.0.0.1 only: nothing on your network can reach it; Tailscale Funnel forwards your public
  https://<pc>.<tailnet>.ts.net address to it (TLS ends on this PC, Tailscale cannot read the traffic);
- every request needs the key (a 256-bit random secret, %APPDATA%\\VoiceTyperHome\\key.txt), compared in
  constant time; after 10 wrong keys in a minute, everything is refused for a minute;
- size limits (5 min of audio, 200 kB of text), zip-bomb safe audio, one dictation at a time on the GPU;
- nothing is written to disk: no audio, no text, no log of the content.

API (JSON answers):
  GET  /v1/ping        → {"ok", "version", "whisper", "writer", "device"}
  POST /v1/transcribe  ← zlib(16-bit PCM), header X-VT-Options {"language","hotwords","mode","sample_rate"}
                       → {"text", "seconds"}
  POST /v1/rewrite     ← {"text","instructions","signature","signature_en","add_signature","subject",
                          "signature_blank_line","language"} → {"text", "timings"}
"""

import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_AUDIO_SECONDS = 300
SAMPLE_RATE = 16000
MAX_BODY = 10 * 1024 * 1024
MAX_TEXT = 200_000
LOCK_AFTER = 10            # wrong keys …
LOCK_WINDOW = 60.0         # … within this many seconds → refuse everything for LOCK_WINDOW


def home_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "VoiceTyperHome"


def load_or_create_key(folder: Path | None = None) -> str:
    folder = folder or home_dir()
    path = folder / "key.txt"
    if path.is_file():
        key = path.read_text(encoding="utf-8").strip()
        if len(key) >= 32:
            return key
    folder.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    path.write_text(key, encoding="utf-8")
    return key


class Models:
    """Whisper + writing AI, loaded from this PC's own Voice Typer settings (same models you chose there)."""

    def __init__(self):
        self.transcriber = None
        self.writer = None
        self.whisper_name = ""
        self.writer_name = ""
        self.error = ""
        self.gpu = threading.Lock()   # one job at a time on the graphics card

    def load(self, log=print) -> None:
        from voice_typer import models, speed
        from voice_typer.config import Config
        from voice_typer.transcriber import Transcriber

        cfg = Config.load()
        source = cfg.model or "large-v3-turbo"
        log(f"Chargement de Whisper : {source} …")
        path = models.resolve(source)
        self.transcriber = models.retry_while_locked(lambda: Transcriber(
            source, path, cfg.device, cfg.compute_type, cfg.gpu_compute_type,
            cpu_threads=speed.cpu_threads(cfg.all_cores)))
        self.whisper_name = source
        log(f"  prêt sur {'la carte graphique' if self.transcriber.device == 'cuda' else 'le processeur'}")
        if cfg.writing_model:
            try:
                from voice_typer.writer import Writer

                log(f"Chargement de l'IA d'écriture : {cfg.writing_model} …")
                self.writer = models.retry_while_locked(lambda: Writer(
                    cfg.writing_model, cfg.device, "int8", "int8_float16",
                    cpu_threads=speed.cpu_threads(cfg.all_cores)))
                self.writer_name = cfg.writing_model
                log("  prête")
            except Exception as exc:  # noqa: BLE001 — transcription still works without it
                self.error = f"IA d'écriture : {exc}"
                log(f"  impossible : {exc}")

    @property
    def device(self) -> str:
        return getattr(self.transcriber, "device", "")

    def transcribe(self, audio, language, hotwords, mode) -> str:
        with self.gpu:
            return self.transcriber.transcribe(audio, language, hotwords, mode=mode)

    def rewrite(self, req: dict) -> tuple[str, dict]:
        with self.gpu:
            out = self.writer.rewrite(
                req["text"], req.get("instructions", ""), req.get("signature", ""),
                bool(req.get("add_signature")), bool(req.get("subject")),
                signature_blank_line=bool(req.get("signature_blank_line")),
                signature_en=req.get("signature_en", "") or "", language=req.get("language"))
            return out, dict(getattr(self.writer, "last_timings", {}) or {})


class Guard:
    """Wrong-key counter: after LOCK_AFTER failures within LOCK_WINDOW seconds, refuse all for LOCK_WINDOW."""

    def __init__(self, key: str, clock=time.monotonic):
        self.key = key.encode("utf-8")
        self.clock = clock
        self.failures: list[float] = []
        self.locked_until = 0.0
        self.lock = threading.Lock()

    def check(self, header: str | None) -> str:
        """"ok", "bad_key" or "locked"."""
        with self.lock:
            now = self.clock()
            if now < self.locked_until:
                return "locked"
            given = (header or "").removeprefix("Bearer ").strip().encode("utf-8")
            if hmac.compare_digest(given, self.key):
                return "ok"
            self.failures = [t for t in self.failures if now - t < LOCK_WINDOW] + [now]
            if len(self.failures) >= LOCK_AFTER:
                self.locked_until = now + LOCK_WINDOW
                self.failures = []
            return "bad_key"


def _str_or_none(v, allowed=None):
    if v is None or (isinstance(v, str) and (allowed is None or v in allowed)):
        return v
    raise ValueError("bad option")


def handle(models: Models, guard: Guard, method: str, path: str, headers, body: bytes,
           version: str = "") -> tuple[int, dict]:
    """The whole API, without sockets (unit-tested). Returns (HTTP status, JSON answer)."""
    from voice_typer import home

    auth = guard.check(headers.get("Authorization"))
    if auth != "ok":
        return (429 if auth == "locked" else 401), {"error": auth}
    if method == "GET" and path == "/v1/ping":
        return 200, {"ok": True, "version": version, "whisper": models.whisper_name,
                     "writer": models.writer_name, "device": models.device}
    if method != "POST" or path not in ("/v1/transcribe", "/v1/rewrite"):
        return 404, {"error": "not_found"}
    if len(body) > MAX_BODY:
        return 413, {"error": "too_long"}
    try:
        if path == "/v1/transcribe":
            if models.transcriber is None:
                return 503, {"error": "loading"}
            opts = json.loads(headers.get("X-VT-Options") or "{}")
            if not isinstance(opts, dict) or opts.get("sample_rate", SAMPLE_RATE) != SAMPLE_RATE:
                return 400, {"error": "bad_options"}
            language = _str_or_none(opts.get("language"), {"fr", "en"})
            hotwords = _str_or_none(opts.get("hotwords"))
            mode = _str_or_none(opts.get("mode"), {"auto", "fast", "accurate"}) or "auto"
            try:
                audio = home.decode_audio(body, MAX_AUDIO_SECONDS * SAMPLE_RATE * 2)
            except ValueError:
                return 413, {"error": "too_long"}
            started = time.perf_counter()
            text = models.transcribe(audio, language, (hotwords or "")[:2000] or None, mode)
            return 200, {"text": text, "seconds": round(time.perf_counter() - started, 3)}
        # /v1/rewrite
        if models.writer is None:
            return 503, {"error": "no_writer"}
        if len(body) > MAX_TEXT:
            return 413, {"error": "too_long"}
        req = json.loads(body.decode("utf-8"))
        if not isinstance(req, dict) or not isinstance(req.get("text"), str):
            return 400, {"error": "bad_request"}
        for k in ("instructions", "signature", "signature_en"):
            if not isinstance(req.get(k, ""), str):
                return 400, {"error": "bad_request"}
        _str_or_none(req.get("language"), {"fr", "en"})
        text, timings = models.rewrite(req)
        return 200, {"text": text, "timings": timings}
    except (ValueError, UnicodeDecodeError):
        return 400, {"error": "bad_request"}


def make_server(models: Models, key: str, port: int, version: str = "", host: str = "127.0.0.1"):
    guard = Guard(key)

    class Handler(BaseHTTPRequestHandler):
        server_version = "VoiceTyperHome"
        sys_version = ""

        def _run(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                status, answer = 413, {"error": "too_long"}
                self.close_connection = True
            else:
                body = self.rfile.read(length) if length > 0 else b""
                try:
                    status, answer = handle(models, guard, method, self.path, self.headers, body, version)
                except Exception as exc:  # noqa: BLE001 — answer, never crash the server
                    print(f"Erreur : {type(exc).__name__}: {exc}")
                    status, answer = 500, {"error": "internal"}
            data = json.dumps(answer).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            self._run("GET")

        def do_POST(self):  # noqa: N802
            self._run("POST")

        def log_message(self, fmt, *args):  # one short line per request, never the content
            print(f"{time.strftime('%H:%M:%S')} {self.command} {self.path.split('?')[0]} → {args[1] if len(args) > 1 else ''}")

    return ThreadingHTTPServer((host, port), Handler)
