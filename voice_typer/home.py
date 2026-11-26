"""« PC à la maison »: send the dictation to Home Connections running on the user's own computer.

The home PC (with an NVIDIA card) runs Home Connections (its own repo) behind Tailscale Funnel, which gives it a public HTTPS
address (https://<pc>.<tailnet>.ts.net). This module is only a CLIENT: plain outbound HTTPS requests, like
the update check. Nothing listens on this PC (IT requirement, tests/test_no_network_server.py).

- `transcribe()` sends 16-bit audio (zlib-compressed) and gets Whisper's raw text back; clean-up, numbers,
  dictionary and voice commands still run here, with this PC's settings.
- `rewrite()` sends the text to the home writing AI (same signature/subject rules: compose.py runs there).
- `wake()` asks the home PC to load the models now, when a recording starts (hides the reload after sleep).
- Every request carries the key as "Authorization: Bearer …" and "X-App: voicetyper-pc". On any failure the caller falls back to the
  local models, so a home PC that is off or asleep only costs the connection timeout.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
import zlib

import numpy as np

CONNECT_TIMEOUT = 4.0   # seconds before giving up on an unreachable home PC


class HomeError(Exception):
    pass


def normalize_url(url: str) -> str:
    """'home-pc.tail1234.ts.net' → 'https://home-pc.tail1234.ts.net'. HTTPS only (http just for this PC)."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    local = parts.hostname in ("127.0.0.1", "localhost")
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        raise HomeError("https_required")
    if not parts.hostname:
        raise HomeError("bad_url")
    return url


def parse_connection_code(text: str) -> tuple[str, str]:
    """« Coller depuis Home Connections »: the code Home Connections copies (« Copier le code de connexion »),
    '<address>#key=<key>' → (address, key). Either can be "" when the text only holds the other one (a bare key, or
    just the address). HomeError("bad_code") when it holds neither. Same rules as Home Connections'
    settings.parse_connection_code and the phone apps."""
    import re

    text = (text or "").strip()
    is_key = re.compile(r"[A-Za-z0-9_-]{32,}").fullmatch
    if "#key=" in text:
        address, _, key = text.partition("#key=")
        address, key = address.strip().rstrip("/"), key.strip()
        if address.startswith(("https://", "http://")) and is_key(key):
            return address, key
        raise HomeError("bad_code")
    if is_key(text):
        return "", text
    if text.startswith(("https://", "http://")) and " " not in text:
        return text.rstrip("/"), ""
    raise HomeError("bad_code")


def encode_audio(audio: np.ndarray) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    return zlib.compress(pcm, 6)


def decode_audio(data: bytes, max_bytes: int) -> np.ndarray:
    """Inverse of encode_audio, refusing anything that inflates beyond max_bytes (zip bomb)."""
    d = zlib.decompressobj()
    pcm = d.decompress(data, max_bytes + 1)
    if len(pcm) > max_bytes or d.unconsumed_tail:
        raise ValueError("audio too long")
    if len(pcm) % 2:
        pcm = pcm[:-1]
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32767.0


def _open(req, timeout):  # patched by the tests
    return urllib.request.urlopen(req, timeout=timeout)


class HomeClient:
    def __init__(self, url: str, key: str):
        self.url = normalize_url(url)
        self.key = (key or "").strip()
        self.last_answer: dict = {}      # the whole JSON answer of the last request (model, device…)
        if not self.url or not self.key:
            raise HomeError("not_configured")

    def _request(self, path: str, body: bytes | None, timeout: float, headers: dict | None = None) -> dict:
        req = urllib.request.Request(self.url + path, data=body, method="POST" if body is not None else "GET")
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("User-Agent", "VoiceTyper")
        req.add_header("X-App", "voicetyper-pc")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with _open(req, timeout) as resp:
                answer = json.loads(resp.read(2_000_000).decode("utf-8"))
                self.last_answer = answer if isinstance(answer, dict) else {}
                return self.last_answer
        except urllib.error.HTTPError as exc:
            reason = {401: "bad_key", 403: "bad_key", 429: "locked", 413: "too_long", 500: "http_500",
                      503: "http_503"}.get(exc.code, "bad_answer")
            raise HomeError(reason) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HomeError("unreachable") from exc
        except ValueError as exc:
            raise HomeError("bad_answer") from exc

    def ping(self) -> dict:
        return self._request("/v1/ping", None, CONNECT_TIMEOUT + 4)

    def wake(self, models: dict) -> dict:
        """{"whisper": "large-v3-turbo", "writer": "…"}: start loading these now (answer at once)."""
        return self._request("/v1/wake", json.dumps({"models": models}).encode("utf-8"), CONNECT_TIMEOUT + 2,
                             {"Content-Type": "application/json"})

    def transcribe(self, audio: np.ndarray, sample_rate: int, language: str | None, hotwords: str | None,
                   mode: str, model: str | None = None) -> str:
        """model: the Whisper model selected on this PC — the home PC loads the same one."""
        options = json.dumps({"language": language, "hotwords": hotwords or None, "mode": mode,
                              "sample_rate": sample_rate, "model": model or None})
        seconds = audio.size / float(sample_rate)
        out = self._request("/v1/transcribe", encode_audio(audio), CONNECT_TIMEOUT + 10 + seconds,
                            {"Content-Type": "application/octet-stream", "X-VT-Options": options})
        if not isinstance(out.get("text"), str):
            raise HomeError("bad_answer")
        return out["text"]

    def rewrite(self, text: str, instructions: str, signature: str, add_signature: bool, subject: bool,
                signature_blank_line: bool, signature_en: str, language: str | None,
                writing_model: str | None = None) -> tuple[str, dict]:
        payload = {"writing_model": writing_model or None, "text": text, "instructions": instructions,
                   "signature": signature,
                   "add_signature": add_signature, "subject": subject,
                   "signature_blank_line": signature_blank_line, "signature_en": signature_en,
                   "language": language}
        out = self._request("/v1/rewrite", json.dumps(payload).encode("utf-8"), CONNECT_TIMEOUT + 60,
                            {"Content-Type": "application/json"})
        if not isinstance(out.get("text"), str):
            raise HomeError("bad_answer")
        timings = out.get("timings") if isinstance(out.get("timings"), dict) else {}
        return out["text"], {k: float(v) for k, v in timings.items() if isinstance(v, (int, float))}
