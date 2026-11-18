"""Automatic updates from the public releases repository.

Each release on https://github.com/hugocodings-design/Voice-Typer-Releases carries two files:
the installer and `latest.json` (written by installer/publish.ps1):

    {"version": "0.8.0", "url": "https://github.com/.../VoiceTyperSetup-0.8.0.exe",
     "sha256": "…", "size": 600000000, "notes_fr": "…", "notes_en": "…"}

latest.json is signed (ed25519, field "signature", made by installer/sign.py with a private key
that never leaves the publisher's PC). The app checks it against UPDATE_PUBLIC_KEY and refuses any
unsigned or wrongly signed manifest: taking over the GitHub account is not enough to ship code.
Copies older than 0.9.0 ignore the extra field, so they still receive signed releases.

The app reads latest.json, and if the version is newer, offers to download the installer, checks
its SHA-256 (a tampered or truncated file is never run), then runs it silently with /UPDATE=1:
the installer closes the app, keeps settings / history / models, and starts the new version.
Only installed (frozen) copies update themselves; a dev checkout uses git.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from voice_typer import __version__

REPO = "hugocodings-design/Voice-Typer-Releases"
MANIFEST_URL = f"https://github.com/{REPO}/releases/latest/download/latest.json"
ALLOWED_PREFIX = f"https://github.com/{REPO}/releases/download/"
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "VoiceTyperUpdate"
USER_AGENT = f"VoiceTyper/{__version__}"


class UpdateError(Exception):
    pass


def can_self_update() -> bool:
    return bool(getattr(sys, "frozen", False))


def parse_version(v: str) -> tuple[int, ...]:
    out = []
    for part in str(v).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def signed_bytes(info: dict) -> bytes:
    """What the signature covers: every field except "signature", in a canonical form."""
    payload = {k: v for k, v in info.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_signature(info: dict, public_key: str | None = None) -> None:
    """Raises UpdateError unless the manifest carries a valid signature from the publisher's key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if public_key is None:
        from voice_typer.update_key import UPDATE_PUBLIC_KEY as public_key
    sig = info.get("signature")
    if not isinstance(sig, str) or not sig:
        raise UpdateError("unsigned update: refused")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key))
        key.verify(base64.b64decode(sig, validate=True), signed_bytes(info))
    except (InvalidSignature, ValueError) as exc:
        raise UpdateError("bad signature: the update was not published by Voice Typer, refused") from exc


def validate(info: dict, public_key: str | None = None) -> dict:
    """Raises UpdateError if the manifest is unsigned / badly signed, malformed, or points outside
    the releases repository."""
    if not isinstance(info, dict):
        raise UpdateError("bad manifest")
    verify_signature(info, public_key)
    try:
        version, url, sha = str(info["version"]), str(info["url"]), str(info["sha256"]).lower()
        size = int(info.get("size") or 0)
    except (KeyError, TypeError, ValueError) as exc:
        raise UpdateError(f"bad manifest: {exc}") from exc
    if not url.startswith(ALLOWED_PREFIX):
        raise UpdateError("download URL outside the releases repository")
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise UpdateError("bad sha256")
    return {**info, "version": version, "url": url, "sha256": sha, "size": size}


def is_required(info: dict | None) -> bool:
    """A required update (publish.ps1 -Required): installed without asking, "skip" ignored.

    Only trusted after validate(): the flag is covered by the signature."""
    return bool(info and info.get("required") is True)


def _open(url: str, timeout: float):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 — https only (see validate)


def check(timeout: float = 10, manifest_url: str = MANIFEST_URL, public_key: str | None = None) -> dict | None:
    """The newer release's manifest, or None if up to date. Raises UpdateError when offline etc."""
    try:
        with _open(manifest_url, timeout) as resp:
            info = json.loads(resp.read(65536))
    except Exception as exc:  # noqa: BLE001 — offline, 404 (no release yet), garbage
        raise UpdateError(str(exc)) from exc
    info = validate(info, public_key)
    return info if is_newer(info["version"]) else None


def download(info: dict, progress=None, cancelled=lambda: False) -> Path:
    """Downloads the installer, verifying its SHA-256. progress(done_bytes, total_bytes)."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = DOWNLOAD_DIR / f"VoiceTyperSetup-{info['version']}.exe"
    part = dest.with_suffix(".part")
    sha = hashlib.sha256()
    done = 0
    try:
        with _open(info["url"], 60) as resp, open(part, "wb") as f:
            total = int(resp.headers.get("Content-Length") or info.get("size") or 0)
            while True:
                if cancelled():
                    raise UpdateError("cancelled")
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001
        part.unlink(missing_ok=True)
        raise UpdateError(str(exc)) from exc
    if sha.hexdigest() != info["sha256"]:
        part.unlink(missing_ok=True)
        raise UpdateError("checksum mismatch: the downloaded file is damaged or was altered")
    part.replace(dest)
    return dest


def install(setup: Path) -> None:
    """Starts the installer detached, after a short pause so this process can exit first.

    The caller must quit the app right after. /UPDATE=1 makes the installer start the new version.
    """
    args = f'"{setup}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /UPDATE=1'
    cmd = f'ping -n 6 127.0.0.1 >nul & start "" {args}'
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    # Passed as one string: a list would make Python escape the quotes as \" which cmd misreads.
    subprocess.Popen(f"cmd.exe /c {cmd}", creationflags=flags, close_fds=True,  # noqa: S603
                     cwd=os.path.dirname(setup))


def cleanup() -> None:
    """Deletes installers left from a previous update (called once the new version runs)."""
    for f in DOWNLOAD_DIR.glob("VoiceTyperSetup-*"):
        try:
            f.unlink()
        except OSError:
            pass
