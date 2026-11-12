"""Engine part: sharing AI power between PCs (host server / client connection, remote.py)."""

import threading
import time

from voice_typer.transcriber import Transcriber


class RemoteMixin:
    def local_transcriber(self) -> Transcriber | None:
        return self.transcriber

    def apply_remote(self) -> None:
        """Start / stop the home server or the client connection to match the settings."""
        from voice_typer import remote

        cfg = self.config
        if cfg.remote_mode == "host":
            if not cfg.host_key:
                cfg.host_key = remote.new_key()
                cfg.save()
            if self.host and (self.host.port != cfg.host_port or self.host.key != cfg.host_key
                              or self.host.allow_internet != cfg.host_allow_internet):
                self.host.stop()
                self.host = None
            if self.host is None:
                try:
                    host = remote.Host(self, cfg.host_port, cfg.host_key, allow_internet=cfg.host_allow_internet)
                    host.start()
                    self.host = host
                except (OSError, ValueError) as exc:  # port already used, certificate unreadable…
                    self._emit("host_error", str(exc))
            self.remote = None
            self.remote_status = None
        else:
            if self.host:
                self.host.stop()
                self.host = None
            if cfg.remote_mode == "client" and cfg.remote_url and cfg.remote_key:
                if not cfg.client_id:
                    import uuid

                    cfg.client_id = uuid.uuid4().hex
                    cfg.save()
                self.remote = remote.Client(cfg.remote_url, cfg.remote_key, cfg.client_id,
                                            fingerprint=cfg.remote_fingerprint)
                self.remote_status = None
                threading.Thread(target=self.check_remote, daemon=True).start()
            else:
                self.remote = None
                self.remote_status = None
        self._emit("remote_changed")

    def check_remote(self) -> None:
        client = self.remote
        if client is None:
            return
        from voice_typer.remote import RemoteError

        try:
            t0 = time.perf_counter()
            info = client.ping()
            info["ms"] = round((time.perf_counter() - t0) * 1000)
            self._set_remote_status(True, info)
        except RemoteError as exc:
            self._set_remote_status(False, str(exc))

    def _set_remote_status(self, ok: bool, info: object = None) -> None:
        if ok and info is None and self.remote_status and self.remote_status[0]:
            return  # still fine: keep the details from the last ping
        self.remote_status = (ok, info)
        self._emit("remote_status", self.remote_status)

    def _remote_failed(self, exc: Exception) -> None:
        self._set_remote_status(False, str(exc))
        self._emit("remote_down", str(exc))

    def _remote_transcribe(self, audio, language, hotwords) -> str | None:
        """Text from the home PC, or None if it can't be reached (then this PC does it)."""
        if self.remote is None:
            return None
        from voice_typer.remote import RemoteError

        try:
            text = self.remote.transcribe(audio, language, hotwords)
            self._set_remote_status(True)
            return text
        except RemoteError as exc:
            self._remote_failed(exc)
            return None
