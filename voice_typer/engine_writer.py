"""Engine part: AI writing presets and the local writing AI (load / unload / rewrite)."""

import threading
import time
import traceback

from voice_typer import models
from voice_typer.speed import cpu_threads
from voice_typer.hotkey import Hotkey


class WriterMixin:
    def preset(self, preset_id: str | None) -> dict | None:
        return next((p for p in self.config.presets or [] if p.get("id") == preset_id), None)

    def _build_preset_hotkeys(self) -> None:
        for hk in self.preset_hotkeys.values():
            hk.stop()
        self.preset_hotkeys = {}
        for p in self.config.presets or []:
            if not p.get("hotkey"):
                continue
            pid = p["id"]
            try:
                hk = Hotkey(p["hotkey"], lambda pid=pid: self._on_down(pid), lambda pid=pid: self._on_up(pid))
            except Exception:  # noqa: BLE001 — invalid combo in settings.json: skip it
                continue
            self.preset_hotkeys[pid] = hk
            if self._hotkeys_running:
                hk.start()

    def apply_presets(self) -> None:
        """Call after editing config.presets: saves them and re-registers their shortcuts."""
        self.config.save()
        self._build_preset_hotkeys()
        if self.config.writer_preload and self.preset_hotkeys:
            from voice_typer import writer

            if writer.is_downloaded(self.config.writing_model):
                self.load_writer()

    def _make_writer(self):
        from voice_typer.writer import Writer

        return models.retry_while_locked(
            lambda: Writer(self.config.writing_model, self.config.device, "int8", "int8_float16",
                           cpu_threads=cpu_threads(self.config.all_cores)))

    def load_writer(self, force: bool = False) -> None:
        """Download (if needed) and load the writing AI in the background."""
        if self.writer_loading:
            return
        if self.writer is not None and not force and self.writer.source == self.config.writing_model:
            return
        self.writer_loading = True
        source = self.config.writing_model
        self._emit("writer_loading", source)

        def work():
            try:
                started = time.perf_counter()
                with self._writer_lock:
                    # A dictation may have loaded it while we waited for the lock.
                    if force or self.writer is None or self.writer.source != source:
                        self.writer = None      # free GPU memory before loading another one
                        self.writer = self._make_writer()
                self._emit("writer_loaded", (source, self.writer.device, time.perf_counter() - started))
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self._emit("writer_error", f"{type(exc).__name__}: {exc}")
            finally:
                self.writer_loading = False

        threading.Thread(target=work, daemon=True).start()

    def unload_writer(self) -> None:
        with self._writer_lock:
            self.writer = None
        self._emit("writer_unloaded")

    def rewrite(self, text: str, preset: dict) -> str:
        """Blocking: rewrite text with a preset."""
        instructions = preset.get("instructions", "")
        from voice_typer.compose import preset_flags

        add_signature, subject = preset_flags(preset)
        client = self.home_client()
        if client is not None:   # « PC à la maison »: same rules, run on the home PC's graphics card
            from voice_typer import home

            try:
                out, timings = client.rewrite(text, instructions, self.config.signature, add_signature, subject,
                                              self.config.signature_blank_line, self.config.signature_en,
                                              self.config.language)
                self.last_rewrite_timings = timings
                self._home_result(True)
                return out
            except home.HomeError as exc:
                self._home_result(False, str(exc))
        return self.rewrite_local(text, instructions, self.config.signature, add_signature, subject)

    def rewrite_local(self, text: str, instructions: str, signature: str, add_signature: bool = False,
                      subject: bool = False) -> str:
        """Blocking: rewrite on this PC, loading the writing AI first if needed."""
        with self._writer_lock:
            if self.writer is None or self.writer.source != self.config.writing_model:
                source = self.config.writing_model
                self._emit("writer_loading", source)
                started = time.perf_counter()
                self.writer = self._make_writer()
                self._emit("writer_loaded", (source, self.writer.device, time.perf_counter() - started))
            writer = self.writer
            out = writer.rewrite(text, instructions, signature, add_signature, subject,
                                 signature_blank_line=self.config.signature_blank_line,
                                 signature_en=self.config.signature_en, language=self.config.language)
            self.last_rewrite_timings = dict(getattr(writer, "last_timings", {}) or {})
            if not self.config.writer_preload:
                self.writer = None
            return out
