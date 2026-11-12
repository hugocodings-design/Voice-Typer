"""Shortcut recorder dialog + conflict checks."""

import threading
import tkinter as tk
from tkinter import ttk

from voice_typer.gui import dialogs as messagebox

import keyboard

from voice_typer import ui_theme
from voice_typer.gui.common import (LANG_PRESETS, PASTE_PRESETS, PRESETS, REWRITE_PRESETS, UNDO_PRESETS,
                                    WRITING_PRESET_KEYS)
from voice_typer.hotkey import normalize as normalize_hotkey
from voice_typer.hotkey import validate as validate_hotkey
from voice_typer.i18n import pretty_hotkey


class ShortcutRecorder:
    # ================================================================== shortcut recording
    def _set_lang_hotkey(self, combo: str) -> None:
        self.engine.set_language_hotkey(combo)
        self._build()

    def _record_hotkey(self, target: str) -> None:
        if self._rec_dialog is not None:
            return
        self._rec_target = target
        self.engine.pause_hotkey()
        dlg = self._rec_dialog = tk.Toplevel(self.root)
        dlg.title(self.t("rec_title"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.configure(bg=self.pal["bg"])
        dlg.protocol("WM_DELETE_WINDOW", self._close_recorder)
        box = ttk.Frame(dlg, padding=24)
        box.pack()
        ttk.Label(box, text=self.t("rec_prompt"), justify="center").pack(pady=(0, 10))
        ttk.Label(box, text=self.t("rec_waiting"), font=self.fonts.status).pack(pady=8)
        ttk.Label(box, text=self.t("rec_presets"), style="Muted.TLabel").pack(pady=(12, 6))
        row = ttk.Frame(box)
        row.pack(pady=(0, 10))
        choices = {"main": PRESETS, "lang": LANG_PRESETS, "paste": PASTE_PRESETS,
                   "rewrite": REWRITE_PRESETS, "undo": UNDO_PRESETS}.get(target, WRITING_PRESET_KEYS)
        taken = self._taken_hotkeys(target)
        for combo in [c for c in choices if c not in taken]:
            ttk.Button(row, text=pretty_hotkey(self.config.ui_language, combo),
                       command=lambda c=combo: self._apply_hotkey(c)).pack(side="left", padx=4)
        ttk.Button(box, text=self.t("cancel"), command=self._close_recorder).pack(pady=(6, 0))
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_reqheight()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        ui_theme._dark_title_bar(dlg, self.mode == "dark")  # noqa: SLF001
        dlg.grab_set()
        dlg.focus_force()
        self._listen_for_hotkey()

    def _listen_for_hotkey(self) -> None:
        self._rec_token += 1
        token = self._rec_token

        def work():
            try:
                combo = keyboard.read_hotkey(suppress=False)
            except Exception:  # noqa: BLE001
                return
            self.call_soon(lambda: self._on_recorded(token, combo))

        threading.Thread(target=work, daemon=True).start()

    def _on_recorded(self, token: int, combo: str) -> None:
        if token != self._rec_token or self._rec_dialog is None:
            return
        if combo.strip().lower() in ("esc", "escape"):
            self._close_recorder()
            return
        error = validate_hotkey(combo)
        pretty = pretty_hotkey(self.config.ui_language, combo)
        owner = self._taken_hotkeys(self._rec_target).get("+".join(normalize_hotkey(combo)))
        if error or owner:
            if error:
                key = {"unknown": "rec_err_unknown"}.get(error, "rec_err_single")
                msg = self.t(key, combo=pretty)
            else:
                msg = self.t("rec_err_taken", combo=pretty, what=owner)
            messagebox.showerror(self.t("rec_err_title"), msg, parent=self._rec_dialog)
            self._listen_for_hotkey()
            return
        self._apply_hotkey(combo)

    def _apply_hotkey(self, combo: str) -> None:
        target = self._rec_target
        self._close_recorder()
        if target == "main":
            self.engine.set_hotkey(combo)
        elif target == "lang":
            self.engine.set_language_hotkey(combo)
        elif target == "paste":
            self.engine.set_paste_last_hotkey(combo)
        elif target == "rewrite":
            self.engine.set_rewrite_hotkey(combo)
        elif target == "undo":
            self.engine.set_undo_hotkey(combo)
        elif target.startswith("preset:"):
            self._set_preset_hotkey(target.split(":", 1)[1], combo)
            return
        self._build()

    def _set_undo_hotkey(self, combo: str) -> None:
        self.engine.set_undo_hotkey(combo)
        self._build()

    def _set_paste_hotkey(self, combo: str) -> None:
        self.engine.set_paste_last_hotkey(combo)
        self._build()

    def _taken_hotkeys(self, target: str) -> dict[str, str]:
        """Shortcuts already used by something other than `target` → who uses them."""
        def norm(c: str) -> str:
            return "+".join(normalize_hotkey(c))

        taken = {}
        if target != "main" and self.config.hotkey:
            taken[norm(self.config.hotkey)] = self.t("rec_target_main")
        if target != "lang" and self.config.language_hotkey:
            taken[norm(self.config.language_hotkey)] = self.t("rec_target_lang")
        if target != "paste" and self.config.paste_last_hotkey:
            taken[norm(self.config.paste_last_hotkey)] = self.t("rec_target_paste")
        if target != "undo" and self.config.undo_hotkey:
            taken[norm(self.config.undo_hotkey)] = self.t("rec_target_undo")
        if target != "rewrite" and self.config.rewrite_hotkey:
            taken[norm(self.config.rewrite_hotkey)] = self.t("rec_target_rewrite")
        for p in self.config.presets or []:
            if p.get("hotkey") and target != f"preset:{p['id']}":
                taken[norm(p["hotkey"])] = f"« {p['name']} »"
        return taken

    def _close_recorder(self) -> None:
        self._rec_token += 1
        if self._rec_dialog is not None:
            self._rec_dialog.grab_release()
            self._rec_dialog.destroy()
            self._rec_dialog = None
        self.engine.resume_hotkey()
