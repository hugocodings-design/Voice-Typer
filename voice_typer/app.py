"""Dictation engine: hotkey → recorder → transcriber → (optional AI rewrite) → output.

The engine never touches the UI directly: it reports what happens through an event queue
that the window polls (tkinter must only be used from the main thread).
"""

import queue
import sys
import threading
import time

from voice_typer import dictionary, models
from voice_typer.config import Config
from voice_typer.hotkey import Hotkey
from voice_typer.output import beep, send_text
from voice_typer.recorder import Recorder
from voice_typer.transcriber import Transcriber

MIN_SECONDS = 0.3     # ignore accidental taps
MAX_SECONDS = 300     # safety stop in toggle mode


class Engine:
    def __init__(self, config: Config):
        self.config = config
        config.ensure_presets()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.transcriber: Transcriber | None = None
        self.loading_source: str | None = None
        self.recorder = Recorder(config.sample_rate)
        self.hotkey = Hotkey(config.hotkey, lambda: self._on_down(None), lambda: self._on_up(None))
        self.lang_hotkey: Hotkey | None = None
        if config.language_hotkey:
            self.lang_hotkey = Hotkey(config.language_hotkey, self.cycle_language, lambda: None)
        # AI writing presets: one global shortcut per preset (dictate, then rewrite)
        self.preset_hotkeys: dict[str, Hotkey] = {}
        self._hotkeys_running = False
        self._build_preset_hotkeys()
        self.writer = None                 # voice_typer.writer.Writer, loaded on demand
        self.writer_loading = False
        self._writer_lock = threading.Lock()
        self._active_preset: str | None = None
        self._record_started = 0.0

    def _emit(self, kind: str, payload: object = None) -> None:
        self.events.put((kind, payload))

    # ---- model --------------------------------------------------------------------------
    def reload_model(self) -> None:
        """Reload the current model (e.g. after switching between GPU and CPU)."""
        source = self.transcriber.source if self.transcriber else self.config.model
        self.load_model(source)

    def load_model(self, source: str) -> None:
        """Download (if needed) and load a model in the background.

        The current model keeps working until the new one is ready, and stays if loading fails.
        """
        if self.loading_source is not None:
            return
        self.loading_source = source
        self._emit("model_loading", source)

        def work():
            try:
                started = time.perf_counter()
                path = models.resolve(source)  # downloads on first use
                new = Transcriber(source, path, self.config.device,
                                  self.config.compute_type, self.config.gpu_compute_type)
                self.transcriber = new
                self.config.model = source
                self.config.save()
                self._emit("model_loaded", (source, time.perf_counter() - started))
                if new.gpu_error:
                    self._emit("gpu_fallback", new.gpu_error)
            except Exception as exc:  # noqa: BLE001
                self._emit("model_error", (source, str(exc)))
            finally:
                self.loading_source = None

        threading.Thread(target=work, daemon=True).start()

    # ---- AI writing (post-processing presets) -------------------------------------------
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

        return Writer(self.config.writing_model, self.config.device, "int8", "int8_float16")

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
                self._emit("writer_error", str(exc))
            finally:
                self.writer_loading = False

        threading.Thread(target=work, daemon=True).start()

    def unload_writer(self) -> None:
        with self._writer_lock:
            self.writer = None
        self._emit("writer_unloaded")

    def rewrite(self, text: str, preset: dict) -> str:
        """Blocking: rewrite text with a preset, loading the writing AI first if needed."""
        with self._writer_lock:
            if self.writer is None or self.writer.source != self.config.writing_model:
                source = self.config.writing_model
                self._emit("writer_loading", source)
                started = time.perf_counter()
                self.writer = self._make_writer()
                self._emit("writer_loaded", (source, self.writer.device, time.perf_counter() - started))
            writer = self.writer
            out = writer.rewrite(text, preset.get("instructions", ""), self.config.signature)
            if not self.config.writer_preload:
                self.writer = None
            return out

    # ---- hotkey -------------------------------------------------------------------------
    def set_hotkey(self, combo: str) -> None:
        self.hotkey.set_combo(combo)
        self.config.hotkey = self.hotkey.combo
        self.config.save()

    def set_language_hotkey(self, combo: str) -> None:
        if self.lang_hotkey:
            self.lang_hotkey.stop()
            self.lang_hotkey = None
        self.config.language_hotkey = combo
        if combo:
            self.lang_hotkey = Hotkey(combo, self.cycle_language, lambda: None)
            self.config.language_hotkey = self.lang_hotkey.combo
            self.lang_hotkey.start()
        self.config.save()

    def pause_hotkey(self) -> None:
        self._hotkeys_running = False
        self.hotkey.stop()
        if self.lang_hotkey:
            self.lang_hotkey.stop()
        for hk in self.preset_hotkeys.values():
            hk.stop()

    def resume_hotkey(self) -> None:
        self._hotkeys_running = True
        self.hotkey.start()
        if self.lang_hotkey:
            self.lang_hotkey.start()
        for hk in self.preset_hotkeys.values():
            hk.start()

    # ---- language -----------------------------------------------------------------------
    def set_language(self, code: str | None) -> None:
        self.config.language = code
        self.config.save()
        self._emit("language_changed", code)

    def cycle_language(self) -> None:
        favs = [c for c in self.config.favorite_languages if c]
        if not favs:
            return
        cur = self.config.language
        nxt = favs[(favs.index(cur) + 1) % len(favs)] if cur in favs else favs[0]
        self.set_language(nxt)

    def _on_down(self, preset_id: str | None) -> None:
        if self.config.mode == "toggle" and self.recorder.is_recording:
            self._finish_recording()
            return
        if self.recorder.is_recording:
            return
        self._active_preset = preset_id
        self._start_recording()

    def _on_up(self, preset_id: str | None) -> None:
        if self.config.mode == "hold" and preset_id == self._active_preset:
            self._finish_recording()

    def _start_recording(self) -> None:
        if self.transcriber is None:
            self._emit("status", "no_model")
            return
        if self.recorder.is_recording:
            return
        self.recorder.device_name = self.config.input_device
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001 — no microphone, device busy…
            self._emit("idle", f"Micro : {exc}")
            return
        if self.config.sounds:
            beep(True)
        self._record_started = time.monotonic()
        self._emit("recording", self.preset(self._active_preset))
        if self.config.mode == "toggle":
            threading.Thread(target=self._safety_stop, args=(self._record_started,), daemon=True).start()

    def _safety_stop(self, started: float) -> None:
        time.sleep(MAX_SECONDS)
        if self.recorder.is_recording and self._record_started == started:
            self._finish_recording()

    def _finish_recording(self) -> None:
        if not self.recorder.is_recording:
            return
        audio = self.recorder.stop()
        if self.config.sounds:
            beep(False)
        if audio.size < MIN_SECONDS * self.config.sample_rate:
            self._emit("idle", "too_short")
            return
        threading.Thread(target=self._transcribe_and_send, args=(audio, self._active_preset),
                         daemon=True).start()

    def _wait_modifiers_released(self, timeout: float = 3.0) -> None:
        # Pasting with Ctrl/Alt still physically held would send e.g. Ctrl+Alt+V instead of Ctrl+V.
        deadline = time.monotonic() + timeout
        keys = [self.hotkey, *self.preset_hotkeys.values()]
        while any(k.modifiers_held() for k in keys) and time.monotonic() < deadline:
            time.sleep(0.03)

    def _transcribe_and_send(self, audio, preset_id: str | None = None) -> None:
        transcriber = self.transcriber
        if transcriber is None:
            return
        self._emit("transcribing")
        try:
            started = time.perf_counter()
            language = self.config.language
            text = transcriber.transcribe(audio, language, dictionary.hotwords(self.config.vocabulary))
            text = dictionary.apply_replacements(text, self.config.replacements)
            raw = text
            preset = self.preset(preset_id)
            if preset and text.strip():
                self._emit("rewriting", preset)
                try:
                    text = self.rewrite(text, preset)
                    text = dictionary.apply_replacements(text, self.config.replacements)
                except Exception as exc:  # noqa: BLE001 — never lose the dictation
                    self._emit("writer_error", str(exc))
                    text = raw
            elapsed = time.perf_counter() - started
            self._wait_modifiers_released()
            send_text(text, self.config.output, self.config.trailing_space and preset is None)
            self._emit("transcript", (text, elapsed, language, preset["name"] if preset else None, raw))
        except Exception as exc:  # noqa: BLE001
            self._emit("idle", f"Error: {exc}")

    # ---- lifecycle ----------------------------------------------------------------------
    def start(self) -> None:
        self.resume_hotkey()
        self.load_model(self.config.model)
        if self.config.writer_preload and self.preset_hotkeys:
            from voice_typer import writer

            if writer.is_downloaded(self.config.writing_model):
                self.load_writer()

    def stop(self) -> None:
        self.pause_hotkey()
        if self.recorder.is_recording:
            self.recorder.stop()


def _already_running() -> bool:
    """Single instance: a second copy would type everything twice."""
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, "VoiceTyper.SingleInstance")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    config = Config.load()
    if _already_running():
        import tkinter as tk
        from tkinter import messagebox

        from voice_typer.i18n import tr

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Voice Typer", tr(config.ui_language, "already_running"))
        root.destroy()
        return

    from voice_typer.gui import Window

    engine = Engine(config)
    Window(engine).run(start_hidden="--minimized" in sys.argv)
