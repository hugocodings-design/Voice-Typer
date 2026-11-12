"""Page Réglages."""

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from voice_typer.gui import dialogs as messagebox

from voice_typer import __version__, autostart
from voice_typer.config import SETTINGS_DIR
from voice_typer.gui.common import ScrollFrame
from voice_typer.gui.common import UI_LANGUAGES, THEMES
from voice_typer.recorder import Recorder, list_microphones


class SettingsPage:
    # ================================================================== page: settings
    def _page_settings(self, page: ttk.Frame) -> None:
        self._page_header(page, "settings")
        scroll = ScrollFrame(page, self.pal["bg"])
        scroll.pack(fill="both", expand=True)
        body = scroll.inner
        inner_pad = {"padx": (0, 14)}

        # Appearance
        c = self._card(body, self.t("set_appearance"), **inner_pad)
        grid = ttk.Frame(c)
        grid.pack(fill="x")
        ttk.Label(grid, text=self.t("set_theme")).grid(row=0, column=0, sticky="w", pady=4)
        self.theme_combo = ttk.Combobox(grid, state="readonly", width=22,
                                        values=[self.t(f"theme_{k}") for k in THEMES])
        self.theme_combo.current(THEMES.index(self.config.theme) if self.config.theme in THEMES else 0)
        self.theme_combo.bind("<<ComboboxSelected>>", self._on_theme)
        self.theme_combo.grid(row=0, column=1, sticky="w", padx=16, pady=4)
        ttk.Label(grid, text=self.t("set_ui_lang")).grid(row=1, column=0, sticky="w", pady=4)
        self.ui_combo = ttk.Combobox(grid, state="readonly", width=22, values=[n for _, n in UI_LANGUAGES])
        codes = [c_ for c_, _ in UI_LANGUAGES]
        self.ui_combo.current(codes.index(self.config.ui_language) if self.config.ui_language in codes else 0)
        self.ui_combo.bind("<<ComboboxSelected>>", self._on_ui_language)
        self.ui_combo.grid(row=1, column=1, sticky="w", padx=16, pady=4)
        self.overlay_var = tk.BooleanVar(value=self.config.overlay)
        ttk.Checkbutton(c, text=self.t("set_overlay"), style="Switch.TCheckbutton", variable=self.overlay_var,
                        command=self._on_overlay).pack(anchor="w", pady=(10, 0))
        self.live_var = tk.BooleanVar(value=self.config.live_preview)
        ttk.Checkbutton(c, text=self.t("set_live"), style="Switch.TCheckbutton", variable=self.live_var,
                        command=self._on_live).pack(anchor="w", pady=(8, 0))
        ttk.Label(c, text=self.t("set_live_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", padx=(46, 0))
        self.live_typing_var = tk.BooleanVar(value=self.config.live_typing)
        ttk.Checkbutton(c, text=self.t("set_live_typing"), style="Switch.TCheckbutton",
                        variable=self.live_typing_var, command=self._on_live_typing).pack(anchor="w", pady=(8, 0))
        ttk.Label(c, text=self.t("set_live_typing_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", padx=(46, 0))

        # Microphone
        c = self._card(body, self.t("set_mic"), self.t("set_mic_sub"), **inner_pad)
        row = ttk.Frame(c)
        row.pack(fill="x")
        self._mics = [None] + list_microphones(refresh=not self.engine.recorder.is_recording)
        names = [self.t("mic_default")] + self._mics[1:]
        if self.config.input_device and self.config.input_device not in self._mics:
            # unplugged: stays the choice, used again by itself once reconnected
            self._mics.append(self.config.input_device)
            names.append(self.t("mic_unplugged", name=self.config.input_device))
        self.mic_combo = ttk.Combobox(row, state="readonly", width=48, values=names)
        self.mic_combo.current(self._mics.index(self.config.input_device))
        self.mic_combo.bind("<<ComboboxSelected>>", self._on_mic)
        self.mic_combo.pack(side="left")
        self.mic_test_btn = ttk.Button(row, text=self.t("mic_test"), command=self._toggle_mic_test)
        self.mic_test_btn.pack(side="left", padx=10)
        ttk.Label(c, text=self.t("mic_remember_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(6, 0))
        self.mic_level = ttk.Progressbar(c, mode="determinate", maximum=100, length=360)
        self.mic_level.pack(anchor="w", pady=(10, 0))
        self.sounds_var = tk.BooleanVar(value=self.config.sounds)
        ttk.Checkbutton(c, text=self.t("set_sounds"), style="Switch.TCheckbutton", variable=self.sounds_var,
                        command=self._on_sounds).pack(anchor="w", pady=(10, 0))

        # Output
        c = self._card(body, self.t("set_output"), **inner_pad)
        self.output_var = tk.StringVar(value=self.config.output)
        for value, key in (("paste", "out_paste"), ("type", "out_type")):
            ttk.Radiobutton(c, text=self.t(key), value=value, variable=self.output_var,
                            command=self._on_output).pack(anchor="w", pady=2)
        self.space_var = tk.BooleanVar(value=self.config.trailing_space)
        ttk.Checkbutton(c, text=self.t("set_trailing_space"), style="Switch.TCheckbutton", variable=self.space_var,
                        command=self._on_space).pack(anchor="w", pady=(10, 0))
        self.keepclip_var = tk.BooleanVar(value=self.config.keep_in_clipboard)
        ttk.Checkbutton(c, text=self.t("set_keep_clipboard"), style="Switch.TCheckbutton",
                        variable=self.keepclip_var, command=self._on_keepclip).pack(anchor="w", pady=(8, 0))

        # Acceleration
        c = self._card(body, self.t("set_accel"), **inner_pad)
        self.device_var = tk.StringVar(value=self.config.device)
        for value, key in (("auto", "accel_auto"), ("cuda", "accel_cuda"), ("cpu", "accel_cpu")):
            ttk.Radiobutton(c, text=self.t(key), value=value, variable=self.device_var,
                            command=self._on_device).pack(anchor="w", pady=2)
        self.accel_var = tk.StringVar()
        ttk.Label(c, textvariable=self.accel_var, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self._render_accel()

        # Startup & history
        c = self._card(body, self.t("set_startup"), **inner_pad)
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(c, text=self.t("set_autostart"), style="Switch.TCheckbutton", variable=self.autostart_var,
                        command=self._on_autostart).pack(anchor="w", pady=2)
        self.history_var = tk.BooleanVar(value=self.config.history_enabled)
        ttk.Checkbutton(c, text=self.t("set_history"), style="Switch.TCheckbutton", variable=self.history_var,
                        command=self._on_history).pack(anchor="w", pady=(8, 2))
        ttk.Button(c, text=self.t("history_clear"), command=self._history_clear).pack(anchor="w", pady=(8, 0))

        # Updates
        self._upd_card(body, inner_pad)

        # Folders & about
        c = self._card(body, self.t("set_about"), **inner_pad)
        ttk.Label(c, text=self.t("about_text", version=__version__), style="Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=self.t("open_models_dir"), command=self._open_models_dir).pack(side="left")
        ttk.Button(row, text=self.t("open_settings_dir"),
                   command=lambda: os.startfile(SETTINGS_DIR)).pack(side="left", padx=6)  # noqa: S606
        ttk.Button(row, text=self.t("diag_export"), command=self._export_diagnostic).pack(side="left")
        ttk.Button(row, text=self.t("wizard_open"), command=lambda: self._open_wizard(force=True)).pack(
            side="left", padx=6)
        ttk.Button(row, text=self.t("btn_quit"), command=self._quit).pack(side="right")

    def _render_accel(self) -> None:
        if not hasattr(self, "accel_var"):
            return
        tr_ = self.engine.transcriber
        if tr_ is not None and tr_.device == "cuda":
            self.accel_var.set(self.t("accel_now_gpu", name=self._gpu_name or "NVIDIA"))
        elif tr_ is not None:
            no_gpu = self.config.device != "cpu" and not self._cuda
            self.accel_var.set(self.t("accel_now_cpu") + ("  —  " + self.t("accel_no_gpu") if no_gpu else ""))
        else:
            self.accel_var.set("")

    def _on_theme(self, _e=None) -> None:
        self.config.theme = THEMES[self.theme_combo.current()]
        self.config.save()
        self._build()

    def _on_ui_language(self, _e=None) -> None:
        self.config.ui_language = UI_LANGUAGES[self.ui_combo.current()][0]
        self.config.save()
        self.tray.refresh()
        self._build()

    def _export_diagnostic(self) -> None:
        from datetime import datetime

        from voice_typer import diagnostic

        default = f"VoiceTyper-diagnostic-{datetime.now():%Y%m%d-%H%M}.zip"
        path = filedialog.asksaveasfilename(parent=self.root, title=self.t("diag_export"), defaultextension=".zip",
                                            initialdir=str(Path.home() / "Desktop"), initialfile=default,
                                            filetypes=[("Zip", "*.zip")])
        if not path:
            return
        try:
            diagnostic.export(path, self.engine)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.t("diag_export"), str(exc), parent=self.root)
            return
        messagebox.showinfo(self.t("diag_export"), self.t("diag_done", path=path), parent=self.root)

    def _on_live_typing(self) -> None:
        self.config.live_typing = self.live_typing_var.get()
        self.config.save()

    def _on_live(self) -> None:
        self.config.live_preview = self.live_var.get()
        self.config.save()
        if self.config.live_preview and not self.config.overlay:  # the preview lives in the indicator
            self.config.overlay = True
            self.overlay_var.set(True)
            self.config.save()

    def _on_overlay(self) -> None:
        self.config.overlay = self.overlay_var.get()
        self.config.save()
        if not self.config.overlay:
            self.overlay.hide()

    def _on_mic(self, _e=None) -> None:
        self.config.input_device = self._mics[self.mic_combo.current()]
        self.config.save()
        if self._mic_test:
            self._stop_mic_test()
            self._toggle_mic_test()

    def _toggle_mic_test(self) -> None:
        if self._mic_test:
            self._stop_mic_test()
            return
        rec = Recorder(self.config.sample_rate)
        rec.device_name = self.config.input_device
        try:
            rec.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.t("set_mic"), str(exc), parent=self.root)
            return
        self._mic_test = rec
        self.mic_test_btn.configure(text=self.t("mic_stop"))
        self._mic_tick()

    def _mic_tick(self) -> None:
        if not self._mic_test:
            return
        try:
            self.mic_level["value"] = min(100, self._mic_test.level * 1200)
        except tk.TclError:
            self._stop_mic_test()
            return
        self.root.after(60, self._mic_tick)

    def _stop_mic_test(self) -> None:
        if self._mic_test:
            self._mic_test.stop()
            self._mic_test = None
        try:
            self.mic_level["value"] = 0
            self.mic_test_btn.configure(text=self.t("mic_test"))
        except (AttributeError, tk.TclError):
            pass

    def _on_sounds(self) -> None:
        self.config.sounds = self.sounds_var.get()
        self.config.save()

    def _on_output(self) -> None:
        self.config.output = self.output_var.get()
        self.config.save()

    def _on_keepclip(self) -> None:
        self.config.keep_in_clipboard = self.keepclip_var.get()
        self.config.save()

    def _on_space(self) -> None:
        self.config.trailing_space = self.space_var.get()
        self.config.save()

    def _on_device(self) -> None:
        if self.device_var.get() == self.config.device:
            return
        self.config.device = self.device_var.get()
        self.config.save()
        self.engine.reload_model()

    def _on_autostart(self) -> None:
        try:
            autostart.set_enabled(self.autostart_var.get())
        except OSError as exc:
            self.autostart_var.set(autostart.is_enabled())
            messagebox.showerror("Voice Typer", str(exc), parent=self.root)

    def _on_history(self) -> None:
        self.config.history_enabled = self.history_var.get()
        self.config.save()
        self._refresh_history()

    def _on_mode(self) -> None:
        self.config.mode = self.mode_var.get()
        self.config.save()
        if not self.engine.recorder.is_recording and self._status[1] == "ok":
            self._set_ready()

    def _open_models_dir(self) -> None:
        from huggingface_hub import constants

        Path(constants.HF_HUB_CACHE).mkdir(parents=True, exist_ok=True)
        os.startfile(constants.HF_HUB_CACHE)  # noqa: S606
