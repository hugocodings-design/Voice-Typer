"""Engine part: global shortcuts (paste last, undo last, rewrite selection, language) and
per-application presets."""

import threading
import time
import traceback

from voice_typer.hotkey import Hotkey
from voice_typer.output import copy_selection, send_text
from voice_typer.undo import char_count


class HotkeysMixin:
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
            text = self.last_text
            self.undo.suspend()
            try:
                send_text(text, self.config.output, False, self.config.keep_in_clipboard)
            finally:
                self.undo.resume()
            self.undo.record(text)
            self._emit("pasted_last", text)

        threading.Thread(target=work, daemon=True).start()

    def set_undo_hotkey(self, combo: str) -> None:
        if self.undo_hotkey:
            self.undo_hotkey.stop()
            self.undo_hotkey = None
        self.config.undo_hotkey = combo
        if combo:
            self.undo_hotkey = Hotkey(combo, self.undo_last, lambda: None)
            self.config.undo_hotkey = self.undo_hotkey.combo
            if self._hotkeys_running:
                self.undo_hotkey.start()
        self.config.save()

    def _hotkey_scan_codes(self) -> set[int]:
        """Keys of our own shortcuts: pressing them doesn't count as « typed since the dictation »."""
        codes: set[int] = set()
        for hk in self._all_hotkeys():
            codes |= hk.trigger_codes
        return codes

    def undo_last(self) -> None:
        """Delete exactly what the last dictation typed (only if that is certainly safe)."""
        if self.recorder.is_recording:
            return
        threading.Thread(target=lambda: (self._wait_modifiers_released(), self._undo_now()), daemon=True).start()

    def _undo_now(self) -> bool:
        text, reason = self.undo.take()
        if reason:
            self._emit("undo_refused", reason)
            return False
        self.undo.suspend()
        try:
            self._erase(char_count(text))
        finally:
            self.undo.resume()
        self._emit("undone", text)
        return True

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

    BUTTON_KEY = "__mic_button__"  # _down_key of a dictation started by the floating button

    def button_dictate(self, preset_id: str | None = None, use_app_preset: bool = True) -> None:
        """Floating mic button: click = start, click again = stop, whatever the shortcut mode.

        The button never takes focus, so the focused application is still the dictation's target.
        preset_id None + use_app_preset: the application's preset (like the main shortcut);
        preset_id None + not use_app_preset: plain dictation, no AI.
        """
        if self.recorder.is_recording:
            self._finish_recording()
            return
        if getattr(self, "busy", False):
            return
        try:
            from voice_typer.winapp import foreground_exe

            self._target_exe = foreground_exe()
        except Exception:  # noqa: BLE001
            self._target_exe = ""
        if preset_id is None and use_app_preset:
            try:
                preset_id = self.preset_for_app(self._target_exe)
            except Exception:  # noqa: BLE001
                preset_id = None
        self._down_key = self.BUTTON_KEY  # releasing a shortcut key must not end it
        self._press_started = None
        self._active_preset = preset_id
        self._start_recording()
        if self.recorder.is_recording and self.config.mode == "hold":
            # in hold mode _start_recording arms no time limit: a forgotten click must not record forever
            threading.Thread(target=self._safety_stop, args=(self._record_started,), daemon=True).start()

    def set_app_preset(self, exe: str, preset_id: str | None) -> None:
        """« Toujours dans cette application » from the button menu (None = no preset for it)."""
        exe = exe.lower()
        self.config.app_presets = [r for r in self.config.app_presets if r.get("app", "").lower() != exe]
        if preset_id:
            self.config.app_presets.append({"app": exe, "preset": preset_id})
        self.config.save()

    def preset_for_app(self, exe: str | None = None) -> str | None:
        """Preset mapped to the focused application (normal dictation key only), else None."""
        if not self.config.app_presets:
            return None
        if exe is None:
            from voice_typer.winapp import foreground_exe

            exe = foreground_exe()
        for rule in self.config.app_presets:
            if rule.get("app", "").lower() == exe and self.preset(rule.get("preset")):
                return rule["preset"]
        return None

    def _all_hotkeys(self) -> list[Hotkey]:
        keys = [self.hotkey, *self.preset_hotkeys.values()]
        keys += [k for k in (self.lang_hotkey, self.paste_hotkey, self.rewrite_hotkey,
                             getattr(self, "undo_hotkey", None)) if k]
        return keys

    def pause_hotkey(self) -> None:
        self._hotkeys_running = False
        for hk in self._all_hotkeys():
            hk.stop()

    def resume_hotkey(self) -> None:
        self._hotkeys_running = True
        for hk in self._all_hotkeys():
            hk.start()

    def set_language(self, code: str | None) -> None:
        self.config.language = code
        self.config.save()
        self._emit("language_changed", code)

    def cycle_language(self) -> None:
        from voice_typer.languages import SUPPORTED

        cur = self.config.language
        nxt = SUPPORTED[(SUPPORTED.index(cur) + 1) % len(SUPPORTED)] if cur in SUPPORTED else SUPPORTED[0]
        self.set_language(nxt)
