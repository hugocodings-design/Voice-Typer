"""Engine part for « PC à la maison » (home.py is the HTTP client; home_server runs on the home PC).

- `home_client()`: the configured home PC (Réglages), or — on the home PC itself — Voice Typer Home running on
  this same computer (found through its key file): then this app uses its models instead of loading a second
  copy on the graphics card (8 GB is not enough for two), and keeps only a processor copy as a fallback.
- a background check every minute keeps `home_info` up to date for the Home page (« connecté —
  carte graphique », « injoignable », « IA sur le processeur »); dictations update it too.
Only outbound connections: nothing listens here (tests/test_no_network_server.py).
"""

import os
import threading
from pathlib import Path

from voice_typer import home

LOCAL_URL = "http://127.0.0.1:8765"
CHECK_EVERY = 60.0


def local_home_key() -> str:
    """Key of Voice Typer Home on THIS computer, if it was ever started here."""
    base = os.environ.get("APPDATA")
    if not base:
        return ""
    try:
        return (Path(base) / "VoiceTyperHome" / "key.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _vram(info: dict) -> dict:
    """Graphics card memory of the home PC from its /v1/ping answer (MiB)."""
    used, total = info.get("vram_used_mb"), info.get("vram_total_mb")
    if isinstance(used, int) and isinstance(total, int) and total > 0:
        return {"vram_used": used, "vram_total": total}
    return {}


class HomeMixin:
    home_info: dict = {"state": "off"}

    def _home_init(self) -> None:
        self.home_info = {"state": "off"}
        self._local_home = False          # Voice Typer Home answers on this same PC
        self._home_stop = threading.Event()
        self._home_lock = threading.Lock()

    # ---- which home PC
    def home_client(self):
        if self.config.home_enabled:
            try:
                return home.HomeClient(self.config.home_url, self.config.home_key)
            except home.HomeError:
                return None
        if getattr(self, "_local_home", False):
            key = local_home_key()
            if key:
                return home.HomeClient(LOCAL_URL, key)
        return None

    def _set_home_info(self, **info) -> None:
        if info != self.home_info:
            before = self.home_info.get("state")
            self.home_info = info
            self._emit("home_status", dict(info))
            if info.get("state") != before and not info.get("local"):
                self._home_writer_policy(info.get("state"))

    def _home_writer_policy(self, state: str | None) -> None:
        """The writing AI kept in memory on THIS PC is only the fallback when a home PC writes the emails:
        free it while the home PC answers (≈3 GB of memory, and the processor), load it back when it stops."""
        if not self.config.home_enabled:
            return
        if state == "ok" and self.writer is not None and not self.writer_loading:
            self.unload_writer()
        elif state == "down" and self.config.writer_preload and self.writer is None and self.preset_hotkeys:
            from voice_typer import writer

            if writer.is_downloaded(self.config.writing_model):
                self.load_writer()

    def _home_result(self, ok: bool, reason: str = "", writer_device: str | None = None) -> None:
        """After each dictation: tell the window when the home PC stops (or starts again) answering — once."""
        previous = self.home_info.get("state")
        state = "ok" if ok else "down"
        if state != getattr(self, "_home_state", "ok"):
            self._emit("home_back" if ok else "home_down", reason)
        self._home_state = state
        info = {k: v for k, v in self.home_info.items() if k not in ("state", "reason")}
        if writer_device:
            info["writer_device"] = writer_device
        if previous != state or writer_device:
            self._set_home_info(state=state, **({"reason": reason} if reason else {}), **info)

    # ---- background check
    def check_home_now(self) -> None:
        threading.Thread(target=self._check_home, daemon=True).start()

    def _check_home(self) -> None:
        with self._home_lock:
            if self.config.home_enabled:
                try:
                    client = home.HomeClient(self.config.home_url, self.config.home_key)
                    info = client.ping()
                    self._set_home_info(state="ok", local=False, device=info.get("device", ""),
                                        writer_device=info.get("writer_device", ""), **_vram(info))
                except home.HomeError as exc:
                    self._set_home_info(state="down", reason=str(exc), local=False)
                return
            key = local_home_key()
            if not key:
                self._local_home = False
                self._set_home_info(state="off")
                return
            try:
                info = home.HomeClient(LOCAL_URL, key).ping()
            except home.HomeError:
                self._local_home = False
                self._set_home_info(state="off")
                return
            self._local_home = True
            self._set_home_info(state="ok", local=True, device=info.get("device", ""),
                                writer_device=info.get("writer_device", ""), **_vram(info))
            self._share_gpu_with_home()

    def _share_gpu_with_home(self) -> None:
        """Voice Typer Home runs here: free the graphics card for it (one copy of each model is enough)."""
        t = self.transcriber
        if t is not None and getattr(t, "device", "") == "cuda" and self.loading_source is None:
            self.load_model(self.config.model, device="cpu")
        if self.writer is not None and getattr(self.writer, "device", "") == "cuda":
            self.unload_writer()

    def _home_watch(self) -> None:
        while not self._home_stop.wait(CHECK_EVERY):
            try:
                self._check_home()
            except Exception:  # noqa: BLE001 — a status line must never break dictation
                pass

    def start_home_watch(self) -> None:
        """At start: look for Voice Typer Home on this PC FIRST (before the speech model goes on the graphics
        card), then check the configured home PC in the background and every minute."""
        try:
            if not self.config.home_enabled and local_home_key():
                self._check_home()
        except Exception:  # noqa: BLE001
            pass
        self.check_home_now()
        threading.Thread(target=self._home_watch, daemon=True).start()

    def stop_home_watch(self) -> None:
        self._home_stop.set()

    def model_device(self) -> str | None:
        """Device for the local speech model: the processor when Voice Typer Home on this PC has the card."""
        return "cpu" if getattr(self, "_local_home", False) else None

