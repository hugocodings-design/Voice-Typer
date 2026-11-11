"""Dictation engine: hotkey → recorder → transcriber → (optional AI rewrite) → output.

The engine never touches the UI directly: it reports what happens through an event queue
that the window polls (tkinter must only be used from the main thread).
"""

import queue
import sys
import threading
import time
import traceback

from voice_typer import commands, dictionary, models
from voice_typer.config import Config
from voice_typer.hotkey import Hotkey
from voice_typer.output import beep, copy_selection, send_text
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
        self.last_text = ""                # last transcription sent (re-typed by paste_last_hotkey)
        self.paste_hotkey: Hotkey | None = None
        if config.paste_last_hotkey:
            try:
                self.paste_hotkey = Hotkey(config.paste_last_hotkey, self.paste_last, lambda: None)
            except Exception:  # noqa: BLE001
                self.paste_hotkey = None
        self.rewrite_hotkey: Hotkey | None = None
        if config.rewrite_hotkey:
            try:
                self.rewrite_hotkey = Hotkey(config.rewrite_hotkey, self.rewrite_selection, lambda: None)
            except Exception:  # noqa: BLE001
                self.rewrite_hotkey = None
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
                new = models.retry_while_locked(lambda: Transcriber(
                    source, path, self.config.device,
                    self.config.compute_type, self.config.gpu_compute_type))
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

        return models.retry_while_locked(
            lambda: Writer(self.config.writing_model, self.config.device, "int8", "int8_float16"))

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

    def set_paste_last_hotkey(self, combo: str) -> None:
        if self.paste_hotkey:
            self.paste_hotkey.stop()
            self.paste_hotkey = None
        self.config.paste_last_hotkey = combo
        if combo:
            self.paste_hotkey = Hotkey(combo, self.paste_last, lambda: None)
            self.config.paste_last_hotkey = self.paste_hotkey.combo
            if self._hotkeys_running:
                self.paste_hotkey.start()
        self.config.save()

    def paste_last(self) -> None:
        """Type the last transcription again (e.g. after it went into the wrong window)."""
        if not self.last_text or self.recorder.is_recording:
            return

        def work():
            self._wait_modifiers_released()
            send_text(self.last_text, self.config.output, False, self.config.keep_in_clipboard)
            self._emit("pasted_last", self.last_text)

        threading.Thread(target=work, daemon=True).start()

    def set_rewrite_hotkey(self, combo: str) -> None:
        if self.rewrite_hotkey:
            self.rewrite_hotkey.stop()
            self.rewrite_hotkey = None
        self.config.rewrite_hotkey = combo
        if combo:
            self.rewrite_hotkey = Hotkey(combo, self.rewrite_selection, lambda: None)
            self.config.rewrite_hotkey = self.rewrite_hotkey.combo
            if self._hotkeys_running:
                self.rewrite_hotkey.start()
        self.config.save()

    def rewrite_selection(self) -> None:
        """Rewrite the text selected in the focused app with the chosen preset, in place."""
        preset = self.preset(self.config.rewrite_preset) or (self.config.presets or [None])[0]
        if preset is None or self.recorder.is_recording:
            return

        def work():
            self._wait_modifiers_released()
            text = copy_selection()
            if not text.strip():
                self._emit("rewrite_empty")
                return
            self._emit("rewriting", preset)
            started = time.perf_counter()
            try:
                out = self.rewrite(text, preset)
            except Exception as exc:  # noqa: BLE001 — leave the selection untouched
                traceback.print_exc()
                self._emit("writer_error", f"{type(exc).__name__}: {exc}")
                self._emit("idle", None)
                return
            self._wait_modifiers_released()
            send_text(out, "paste", False, self.config.keep_in_clipboard)  # pasting replaces the selection
            self.last_text = out
            self._emit("transcript", (out, time.perf_counter() - started, None, preset["name"], text))

        threading.Thread(target=work, daemon=True).start()

    def preset_for_app(self) -> str | None:
        """Preset mapped to the focused application (normal dictation key only), else None."""
        if not self.config.app_presets:
            return None
        from voice_typer.winapp import foreground_exe

        exe = foreground_exe()
        for rule in self.config.app_presets:
            if rule.get("app", "").lower() == exe and self.preset(rule.get("preset")):
                return rule["preset"]
        return None

    def _all_hotkeys(self) -> list[Hotkey]:
        keys = [self.hotkey, *self.preset_hotkeys.values()]
        keys += [k for k in (self.lang_hotkey, self.paste_hotkey, self.rewrite_hotkey) if k]
        return keys

    def pause_hotkey(self) -> None:
        self._hotkeys_running = False
        for hk in self._all_hotkeys():
            hk.stop()

    def resume_hotkey(self) -> None:
        self._hotkeys_running = True
        for hk in self._all_hotkeys():
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
        self._down_key = preset_id  # which key's release ends a hold (None = main dictation key)
        if preset_id is None:
            try:
                preset_id = self.preset_for_app()
            except Exception:  # noqa: BLE001 — never block dictation over this
                preset_id = None
        self._active_preset = preset_id
        self._start_recording()

    def _on_up(self, preset_id: str | None) -> None:
        if self.config.mode == "hold" and preset_id == getattr(self, "_down_key", None):
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
        self._arm_escape()
        self._emit("recording", self.preset(self._active_preset))
        if self.config.live_preview:
            threading.Thread(target=self._live_loop, args=(self._record_started,), daemon=True).start()
        if self.config.mode == "toggle":
            threading.Thread(target=self._safety_stop, args=(self._record_started,), daemon=True).start()

    # ---- Esc cancels the dictation in progress (swallowed so it doesn't also close a dialog)
    def _arm_escape(self) -> None:
        import keyboard

        self._disarm_escape()
        try:
            self._esc_hook = keyboard.on_press_key(
                "esc", lambda _e: threading.Thread(target=self.cancel_recording, daemon=True).start(),
                suppress=True)
        except Exception:  # noqa: BLE001
            self._esc_hook = None

    def _disarm_escape(self) -> None:
        import keyboard

        hook = getattr(self, "_esc_hook", None)
        self._esc_hook = None
        if hook is not None:
            try:
                keyboard.unhook(hook)
            except (KeyError, ValueError):
                pass

    def cancel_recording(self) -> None:
        self._disarm_escape()
        if not self.recorder.is_recording:
            return
        self.recorder.stop()
        if self.config.sounds:
            beep(False)
            beep(False)
        self._emit("cancelled")

    def _live_loop(self, started: float) -> None:
        """While recording, re-transcribe the audio so far and show it (the final pass is redone at the end)."""
        transcriber = self.transcriber
        interval = 0.6 if transcriber and transcriber.device == "cuda" else 1.5
        last = ""
        time.sleep(0.8)
        while self.recorder.is_recording and self._record_started == started and transcriber:
            t0 = time.perf_counter()
            try:
                text = transcriber.preview(self.recorder.snapshot(), self.config.language)
            except Exception:  # noqa: BLE001 — preview is best effort
                traceback.print_exc()
                return
            if text and text != last and self.recorder.is_recording and self._record_started == started:
                last = text
                self._emit("live", text)
            # never use more than ~half the time transcribing (keeps a CPU-only PC responsive)
            time.sleep(max(interval, time.perf_counter() - t0))

    def _safety_stop(self, started: float) -> None:
        time.sleep(MAX_SECONDS)
        if self.recorder.is_recording and self._record_started == started:
            self._finish_recording()

    def _finish_recording(self) -> None:
        self._disarm_escape()
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
        keys = self._all_hotkeys()
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
            if self.config.voice_commands:
                text = commands.apply(text, language)
            raw = text
            preset = self.preset(preset_id)
            if preset and text.strip():
                self._emit("rewriting", preset)
                try:
                    text = self.rewrite(text, preset)
                    text = dictionary.apply_replacements(text, self.config.replacements)
                except Exception as exc:  # noqa: BLE001 — never lose the dictation
                    traceback.print_exc()
                    self._emit("writer_error", f"{type(exc).__name__}: {exc}")
                    text = raw
            elapsed = time.perf_counter() - started
            self._wait_modifiers_released()
            if text:
                self.last_text = text
            send_text(text, self.config.output, self.config.trailing_space and preset is None,
                      self.config.keep_in_clipboard)
            self._emit("transcript", (text, elapsed, language, preset["name"] if preset else None, raw))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
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


def selftest() -> int:
    """`--selftest`: checks a packaged build has everything it needs (run by installer/build.ps1)."""
    try:
        import importlib

        import numpy as np

        for name in ("keyboard", "pystray", "sounddevice", "sv_ttk", "tokenizers",
                     "voice_typer.gui", "voice_typer.transcriber", "voice_typer.writer"):
            importlib.import_module(name)
        from faster_whisper.vad import get_speech_timestamps

        get_speech_timestamps(np.zeros(16000, dtype=np.float32))  # VAD model (onnxruntime)
        from voice_typer import gpu

        print(f"SELFTEST OK cuda_devices={int(gpu.cuda_available())}", flush=True)
        return 0
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("SELFTEST FAILED", flush=True)
        return 1


def main() -> None:
    if "--selftest" in sys.argv:
        sys.exit(selftest())
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
