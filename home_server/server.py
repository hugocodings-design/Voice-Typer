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

Sleep: the models only sit on the graphics card while they are used. Home starts asleep, the first request
wakes both models (Whisper first, then the writing AI) and waits for them (WAKE_WAIT), and IDLE_S seconds
without a dictation or e-mail free the card again for this PC's other programs (TalkTome, Flashcards…).
Pings (every minute from each computer) do not count as use.

API (JSON answers):
  GET  /v1/ping        → {"ok", "version", "whisper", "writer", "device", "asleep"}
  POST /v1/transcribe  ← zlib(16-bit PCM), header X-VT-Options {"language","hotwords","mode","sample_rate"}
                       → {"text", "seconds"}
  POST /v1/rewrite     ← {"text","instructions","signature","signature_en","add_signature","subject",
                          "signature_blank_line","language"} → {"text", "timings"}
"""

import gc
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
IDLE_S = float(os.environ.get("VT_HOME_IDLE_S", "300"))   # free the card after this long unused (0 = never)
# How long a request waits for a sleeping model to load before answering "loading" (the other PC then does
# it itself). Below the client's own timeouts (home.py: 14 s + audio length / 64 s).
WAKE_WAIT = {"whisper": 10.0, "writer": 35.0}
IDLE_CHECK_EVERY = 30.0


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
    """Whisper + writing AI on this PC's graphics card, in the models each computer asks for.

    Each request names the model selected on the computer that sent it ("small", "Français Distil"…). It is
    loaded here the first time (downloaded if needed) and then kept: one Whisper model and one writing model in
    memory at a time (8 GB card). While a model loads, requests get "loading" (503) and the other computer
    does that dictation itself, so nobody waits. Only models from Voice Typer's lists, or imported on THIS PC,
    are accepted; anything else (e.g. a folder on the other computer) uses this PC's own choice instead.
    """

    KINDS = ("whisper", "writer")

    def __init__(self, builders=None, defaults=None, allowed=None, log=print, idle_s: float = IDLE_S,
                 clock=time.monotonic):
        self.log = log
        self.idle_s = idle_s
        self.clock = clock
        self.last_use = clock()
        self.asleep: dict[str, str] = {}   # {kind: source} put to sleep, reloaded by the next request
        self.last_device = {k: "" for k in self.KINDS}   # device while asleep (the laptop shows it)
        self._builders = builders          # {"whisper": fn(source), "writer": fn(source)} — None = real ones
        self.defaults = dict(defaults or {})
        self._allowed = allowed            # {"whisper": set, "writer": set} — None = from the catalogs
        self.objs = {k: None for k in self.KINDS}
        self.names = {k: "" for k in self.KINDS}
        self.loading = {k: None for k in self.KINDS}
        self.failed: dict[str, str] = {}
        self.on_event = None               # fn(kind, source, device, error) after each load (tray notifications)
        from home_server.gpu_memory import Monitor

        self.vram = Monitor()              # graphics card memory (full = the driver spills = very slow)
        self.last_speed: tuple[float, float] | None = None   # (seconds, audio seconds) of the last dictation
        self.state = threading.Lock()
        self.load_lock = threading.Lock()  # one model loads at a time
        self.gpu = threading.Lock()        # one job at a time on the graphics card

    # ---- configuration from this PC's Voice Typer settings
    def configure(self) -> None:
        from voice_typer import models, writer
        from voice_typer.config import Config

        cfg = Config.load()
        custom = {c.get("source") for c in cfg.custom_models if isinstance(c, dict)}
        self.defaults = {"whisper": cfg.model or "large-v3-turbo", "writer": cfg.writing_model or writer.DEFAULT_LLM}
        self._allowed = {"whisper": {m.source for m in models.CATALOG} | custom | {self.defaults["whisper"]},
                         "writer": {m.source for m in writer.LLM_CATALOG} | {self.defaults["writer"]}}
        self._cfg = cfg
        try:
            from voice_typer import gpu

            where = "cuda" if gpu.cuda_available() else "cpu"
        except Exception:  # noqa: BLE001
            where = ""
        for kind in self.KINDS:
            self.last_device[kind] = self.last_device[kind] or where

    def _build(self, kind: str, source: str):
        if self._builders:
            return self._builders[kind](source)
        from voice_typer import models, speed

        cfg = self._cfg
        threads = speed.cpu_threads(cfg.all_cores)
        if kind == "whisper":
            from voice_typer.transcriber import Transcriber

            path = models.resolve(source)
            return models.retry_while_locked(lambda: Transcriber(
                source, path, cfg.device, cfg.compute_type, cfg.gpu_compute_type, cpu_threads=threads))
        from voice_typer.writer import Writer

        return models.retry_while_locked(lambda: Writer(source, cfg.device, "int8", "int8_float16",
                                                        cpu_threads=threads))

    def preload(self) -> None:
        for kind in self.KINDS:
            if self.defaults.get(kind):
                self.get(kind, None)

    def start(self) -> None:
        """At start: asleep (nothing on the card until the first request) with the idle watch, or, with
        IDLE_S = 0, the old behaviour: both models loaded now and kept."""
        if self.idle_s <= 0:
            self.preload()
            return
        with self.state:
            for kind in self.KINDS:
                if self.defaults.get(kind) and self.objs[kind] is None and not self.loading[kind]:
                    self.asleep[kind] = self.defaults[kind]
        self.log(f"En veille : modèles chargés à la première demande, libérés après {self.idle_s / 60:g} min "
                 "sans demande")
        threading.Thread(target=self._idle_watch, daemon=True, name="home-idle").start()

    # ---- the model for a request: ready object, or None while it loads
    def choose(self, kind: str, source: str | None) -> str:
        allowed = (self._allowed or {}).get(kind)
        if not source or (allowed is not None and source not in allowed) or source in self.failed:
            return self.defaults.get(kind, "")
        return source

    def get(self, kind: str, source: str | None, wait: float = 0.0):
        """The model, or None while it loads. A sleeping Home wakes both models (an e-mail needs Whisper,
        then the writing AI right after) and waits up to `wait` seconds for this one."""
        source = self.choose(kind, source)
        with self.state:
            self.last_use = self.clock()
            if self.names[kind] == source and self.objs[kind] is not None:
                return self.objs[kind]
            todo = [(kind, source)]
            for other in self.KINDS:
                if other != kind and other in self.asleep and self.objs[other] is None:
                    todo.append((other, self.asleep[other]))
            for k, _ in todo:
                self.asleep.pop(k, None)
            todo = [(k, s) for k, s in todo if self.loading[k] != s]
            for k, s in todo:
                self.loading[k] = s
        if todo:
            threading.Thread(target=lambda: [self._load(k, s) for k, s in todo], daemon=True).start()
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            time.sleep(0.05)
            with self.state:
                if self.names[kind] == source and self.objs[kind] is not None:
                    self.last_use = self.clock()
                    return self.objs[kind]
                if self.loading[kind] is None:   # failed: the next request uses this PC's own model
                    return None
        return None

    # ---- sleep
    def sleep_if_idle(self) -> bool:
        """Free the graphics card after idle_s seconds without a dictation or e-mail. True if it did."""
        if self.idle_s <= 0:
            return False
        if not self.gpu.acquire(blocking=False):   # a dictation is running
            return False
        try:
            with self.state:
                loaded = [k for k in self.KINDS if self.objs[k] is not None]
                if not loaded or any(self.loading.values()) or self.clock() - self.last_use < self.idle_s:
                    return False
                for k in loaded:
                    self.asleep[k] = self.names[k]
                    self.last_device[k] = getattr(self.objs[k], "device", "") or self.last_device[k]
                    self.objs[k], self.names[k] = None, ""
        finally:
            self.gpu.release()
        gc.collect()
        self.log(f"Inutilisé depuis {self.idle_s / 60:g} min : carte graphique libérée "
                 "(rechargée à la prochaine demande)")
        return True

    def _idle_watch(self) -> None:
        while True:
            time.sleep(IDLE_CHECK_EVERY)
            try:
                self.sleep_if_idle()
            except Exception as exc:  # noqa: BLE001 — never stop watching
                self.log(f"Mise en veille impossible : {exc}")

    def device_of(self, kind: str) -> str:
        """Device of the model, or the one it ran on before going to sleep."""
        obj = self.objs[kind]
        return getattr(obj, "device", "") if obj is not None else (
            self.last_device[kind] if kind in self.asleep else "")

    def name_of(self, kind: str) -> str:
        return self.names[kind] or self.asleep.get(kind, "")

    def _load(self, kind: str, source: str) -> None:
        with self.load_lock:
            if self.loading[kind] != source:
                return                         # another model was asked for meanwhile
            label = "Whisper" if kind == "whisper" else "IA d'écriture"
            self.log(f"Chargement {label} : {source} … (les dictations sont faites sur l'autre PC en attendant)")
            with self.gpu:                     # free the previous one first: the card has 8 GB
                self.objs[kind], self.names[kind] = None, ""
            started = time.perf_counter()
            try:
                obj = self._build(kind, source)
            except Exception as exc:  # noqa: BLE001 — that model won't be asked for again; our own is used
                self.failed[source] = str(exc)
                self.log(f"  impossible : {exc} → modèle de ce PC utilisé à la place")
                obj = None
            with self.state:
                if obj is not None:
                    self.objs[kind], self.names[kind] = obj, source
                    where = "la carte graphique" if getattr(obj, "device", "") == "cuda" else "le processeur"
                    self.log(f"  prêt sur {where} ({time.perf_counter() - started:.0f} s)")
                if self.loading[kind] == source:
                    self.loading[kind] = None
            if self.on_event:
                try:
                    self.on_event(kind, source, getattr(obj, "device", ""), self.failed.get(source, ""))
                except Exception:  # noqa: BLE001 — a notification must never break loading
                    pass

    def status(self) -> dict:
        """{kind: (name, device, loading, asleep)} for the tray menu."""
        return {k: (self.names[k], getattr(self.objs[k], "device", ""), self.loading[k], k in self.asleep)
                for k in self.KINDS}

    def vram_info(self) -> dict:
        """{"vram_used_mb", "vram_total_mb"} for /v1/ping (nothing without nvidia-smi)."""
        value = self.vram.get()
        return {"vram_used_mb": value[0], "vram_total_mb": value[1]} if value else {}

    @property
    def device(self) -> str:
        return getattr(self.objs["whisper"], "device", "")

    def transcribe(self, transcriber, audio, language, hotwords, mode) -> str:
        with self.gpu:
            try:
                return transcriber.transcribe(audio, language, hotwords, mode=mode)
            finally:
                self.last_use = self.clock()   # idle time counts from the END of the work

    def rewrite(self, writer, req: dict) -> tuple[str, dict]:
        with self.gpu:
            try:
                out = writer.rewrite(
                    req["text"], req.get("instructions", ""), req.get("signature", ""),
                    bool(req.get("add_signature")), bool(req.get("subject")),
                    signature_blank_line=bool(req.get("signature_blank_line")),
                    signature_en=req.get("signature_en", "") or "", language=req.get("language"))
                return out, dict(getattr(writer, "last_timings", {}) or {})
            finally:
                self.last_use = self.clock()


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
        return 200, {"ok": True, "version": version, "whisper": models.name_of("whisper"),
                     "writer": models.name_of("writer"), "device": models.device_of("whisper"),
                     "writer_device": models.device_of("writer"),
                     "loading": [v for v in models.loading.values() if v],
                     "asleep": sorted(models.asleep), **models.vram_info()}
    if method != "POST" or path not in ("/v1/transcribe", "/v1/rewrite"):
        return 404, {"error": "not_found"}
    if len(body) > MAX_BODY:
        return 413, {"error": "too_long"}
    try:
        if path == "/v1/transcribe":
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
            transcriber = models.get("whisper", _str_or_none(opts.get("model")), wait=WAKE_WAIT["whisper"])
            if transcriber is None:
                return 503, {"error": "loading"}
            started = time.perf_counter()
            text = models.transcribe(transcriber, audio, language, (hotwords or "")[:2000] or None, mode)
            seconds = time.perf_counter() - started
            models.last_speed = (seconds, audio.size / SAMPLE_RATE)
            models.log(f"{time.strftime('%H:%M:%S')}  dictée     {models.names['whisper']}  {seconds:.1f} s")
            return 200, {"text": text, "seconds": round(seconds, 3), "model": models.names["whisper"]}
        # /v1/rewrite
        if len(body) > MAX_TEXT:
            return 413, {"error": "too_long"}
        req = json.loads(body.decode("utf-8"))
        if not isinstance(req, dict) or not isinstance(req.get("text"), str):
            return 400, {"error": "bad_request"}
        for k in ("instructions", "signature", "signature_en"):
            if not isinstance(req.get(k, ""), str):
                return 400, {"error": "bad_request"}
        _str_or_none(req.get("language"), {"fr", "en"})
        writer = models.get("writer", _str_or_none(req.get("writing_model")), wait=WAKE_WAIT["writer"])
        if writer is None:
            return 503, {"error": "loading"}
        started = time.perf_counter()
        text, timings = models.rewrite(writer, req)
        models.log(f"{time.strftime('%H:%M:%S')}  écriture IA {models.names['writer']}  "
                   f"{time.perf_counter() - started:.1f} s")
        return 200, {"text": text, "timings": timings, "model": models.names["writer"],
                     "device": getattr(writer, "device", "")}
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

        def log_message(self, fmt, *args):  # refused / not-ready requests only, never the content
            status = str(args[1]) if len(args) > 1 else ""
            if status != "200":
                reason = {"401": "clé refusée", "429": "bloqué (trop de mauvaises clés)",
                          "503": "modèle en chargement → fait sur l'autre PC"}.get(status, status)
                print(f"{time.strftime('%H:%M:%S')}  {self.path.split('?')[0]}  {reason}")

    return ThreadingHTTPServer((host, port), Handler)
