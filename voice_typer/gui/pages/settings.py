"""Page Réglages."""

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from voice_typer.gui import dialogs as messagebox

from voice_typer import __version__, autostart, speed
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
        self.fillers_var = tk.BooleanVar(value=self.config.remove_fillers)
        ttk.Checkbutton(c, text=self.t("set_remove_fillers"), style="Switch.TCheckbutton",
                        variable=self.fillers_var, command=self._on_fillers).pack(anchor="w", pady=(8, 0))
        self.numbers_var = tk.BooleanVar(value=self.config.numbers_as_digits)
        ttk.Checkbutton(c, text=self.t("set_numbers_digits"), style="Switch.TCheckbutton",
                        variable=self.numbers_var, command=self._on_numbers).pack(anchor="w", pady=(8, 0))
        self.micbtn_var = tk.BooleanVar(value=self.config.mic_button)
        ttk.Checkbutton(c, text=self.t("set_mic_button"), style="Switch.TCheckbutton",
                        variable=self.micbtn_var, command=self._on_mic_button).pack(anchor="w", pady=(8, 0))
        ttk.Label(c, text=self.t("set_mic_button_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(4, 0))

        # Acceleration
        c = self._card(body, self.t("set_accel"), **inner_pad)
        self.device_var = tk.StringVar(value=self.config.device)
        for value, key in (("auto", "accel_auto"), ("cuda", "accel_cuda"), ("cpu", "accel_cpu")):
            ttk.Radiobutton(c, text=self.t(key), value=value, variable=self.device_var,
                            command=self._on_device).pack(anchor="w", pady=2)
        self.accel_var = tk.StringVar()
        ttk.Label(c, textvariable=self.accel_var, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self._render_accel()

        # Speed (speed.py)
        c = self._card(body, self.t("spd_title"), self.t("spd_sub"), **inner_pad)
        self.speed_var = tk.StringVar(value=self.config.speed_mode)
        for value, key in (("auto", "spd_auto"), ("fast", "spd_fast"), ("accurate", "spd_accurate")):
            ttk.Radiobutton(c, text=self.t(key), value=value, variable=self.speed_var,
                            command=self._on_speed).pack(anchor="w", pady=2)
        self.cores_var = tk.BooleanVar(value=self.config.all_cores)
        ttk.Checkbutton(c, text=self.t("spd_cores", n=speed.cpu_threads(True)), style="Switch.TCheckbutton",
                        variable=self.cores_var, command=self._on_cores).pack(anchor="w", pady=(10, 0))
        ttk.Label(c, text=self.t("spd_ai_hint"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(10, 0))
        ttk.Label(c, text=self.t("spd_timing_hint"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(6, 0))

        # Home PC (home.py → home_server on the user's own computer, through Tailscale Funnel)
        c = self._card(body, self.t("home_title"), self.t("home_sub"), wrap=680, **inner_pad)
        self.home_var = tk.BooleanVar(value=self.config.home_enabled)
        ttk.Checkbutton(c, text=self.t("home_enable"), style="Switch.TCheckbutton", variable=self.home_var,
                        command=self._on_home).pack(anchor="w", pady=(8, 0))
        grid = ttk.Frame(c)
        grid.pack(fill="x", pady=(10, 0))
        ttk.Label(grid, text=self.t("home_url")).grid(row=0, column=0, sticky="w", pady=4)
        self.home_url_var = tk.StringVar(value=self.config.home_url)
        url_entry = ttk.Entry(grid, textvariable=self.home_url_var, width=48)
        url_entry.grid(row=0, column=1, sticky="w", padx=16, pady=4)
        url_entry.bind("<FocusOut>", lambda _e: self._save_home())
        ttk.Label(grid, text=self.t("home_key")).grid(row=1, column=0, sticky="w", pady=4)
        self.home_key_var = tk.StringVar(value=self.config.home_key)
        key_entry = ttk.Entry(grid, textvariable=self.home_key_var, width=48, show="•")
        key_entry.grid(row=1, column=1, sticky="w", padx=16, pady=4)
        key_entry.bind("<FocusOut>", lambda _e: self._save_home())
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(8, 0))
        self.home_test_btn = ttk.Button(row, text=self.t("home_test"), command=self._test_home)
        self.home_test_btn.pack(side="left")
        self.home_test_info = ttk.Label(row, text="", style="Muted.TLabel", wraplength=520, justify="left")
        self.home_test_info.pack(side="left", padx=10)
        ttk.Label(c, text=self.t("home_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(8, 0))

        # Startup & history
        c = self._card(body, self.t("set_startup"), **inner_pad)
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(c, text=self.t("set_autostart"), style="Switch.TCheckbutton", variable=self.autostart_var,
                        command=self._on_autostart).pack(anchor="w", pady=2)
        self.history_var = tk.BooleanVar(value=self.config.history_enabled)
        ttk.Checkbutton(c, text=self.t("set_history"), style="Switch.TCheckbutton", variable=self.history_var,
                        command=self._on_history).pack(anchor="w", pady=(8, 2))
        ttk.Button(c, text=self.t("history_clear"), command=self._history_clear).pack(anchor="w", pady=(8, 0))
        ttk.Label(c, text=self.t("set_close"), style="Muted.TLabel").pack(anchor="w", pady=(14, 2))
        self.close_var = tk.StringVar(value=self.config.close_action)
        for value, key in (("tray", "set_close_tray"), ("quit", "set_close_quit"), ("ask", "set_close_ask")):
            ttk.Radiobutton(c, text=self.t(key), value=value, variable=self.close_var,
                            command=self._on_close_action).pack(anchor="w", pady=2)

        # Move to another PC (transfer.py)
        c = self._card(body, self.t("xfer_title"), self.t("xfer_sub"), **inner_pad)
        ttk.Label(c, text=self.t("xfer_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w")
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=self.t("xfer_export"), command=self._export_settings).pack(side="left")
        ttk.Button(row, text=self.t("xfer_import"), command=self._import_settings).pack(side="left", padx=6)

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
        ttk.Button(row, text=self.t("report_btn"), command=self._report_problem).pack(side="left", padx=(6, 0))
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

    def _report_problem(self) -> None:
        """« Signaler un problème »: a short description, then an e-mail with the diagnostic attached."""
        from voice_typer import report

        self._show_window()
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("report_btn"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.configure(bg=self.pal["bg"])
        box = ttk.Frame(dlg, padding=22)
        box.pack()
        ttk.Label(box, text=self.t("report_intro"), wraplength=460, justify="left").pack(anchor="w")
        text = self._text_box(box, 6)
        text.pack(fill="x", pady=(10, 4))
        ttk.Label(box, text=self.t("report_privacy"), style="Muted.TLabel", wraplength=460,
                  justify="left").pack(anchor="w")

        def send():
            description = text.get("1.0", "end").strip()
            dlg.destroy()
            try:
                path, how = report.prepare(self.engine, description)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror(self.t("report_btn"), str(exc), parent=self.root)
                return
            key = {"outlook": "report_done_outlook", "mailto": "report_done_mailto"}.get(how, "report_done_none")
            messagebox.showinfo(self.t("report_btn"), self.t(key, email=report.SUPPORT_EMAIL, path=str(path)),
                                parent=self.root)

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(16, 0))
        ttk.Button(row, text=self.t("cancel"), command=dlg.destroy).pack(side="right")
        ttk.Button(row, text=self.t("report_send"), style="Accent.TButton", command=send).pack(side="right", padx=6)
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")
        text.focus_set()

    def _export_settings(self) -> None:
        from datetime import datetime

        from voice_typer import transfer

        path = filedialog.asksaveasfilename(
            parent=self.root, title=self.t("xfer_export"), defaultextension=".json",
            initialdir=str(Path.home() / "Desktop"), initialfile=f"VoiceTyper-reglages-{datetime.now():%Y%m%d}.json",
            filetypes=[(self.t("xfer_file_type"), "*.json")])
        if not path:
            return
        try:
            transfer.export_settings(self.config, path)
        except OSError as exc:
            messagebox.showerror(self.t("xfer_export"), str(exc), parent=self.root)
            return
        messagebox.showinfo(self.t("xfer_export"), self.t("xfer_exported", path=path), parent=self.root)

    def _import_settings(self) -> None:
        from voice_typer import transfer

        path = filedialog.askopenfilename(parent=self.root, title=self.t("xfer_import"),
                                          initialdir=str(Path.home() / "Desktop"),
                                          filetypes=[(self.t("xfer_file_type"), "*.json")])
        if not path:
            return
        try:
            settings = transfer.read_export(path)
        except transfer.ImportError_ as exc:
            messagebox.showerror(self.t("xfer_import"), self.t(str(exc)), parent=self.root)
            return
        changes = len(transfer.changes(self.config, settings))
        if not changes:
            messagebox.showinfo(self.t("xfer_import"), self.t("xfer_nothing"), parent=self.root)
            return
        if not messagebox.askyesno(self.t("xfer_import"), self.t("xfer_confirm", count=changes), parent=self.root):
            return
        transfer.apply_settings(self.config, settings)
        self.config.save()
        self._restart()

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

    def _on_speed(self) -> None:
        self.config.speed_mode = self.speed_var.get()   # read at each dictation: no reload needed
        self.config.save()

    def _on_cores(self) -> None:
        self.config.all_cores = self.cores_var.get()
        self.config.save()
        # the thread count is fixed when a model loads: reload the speech model, and the writing AI if loaded
        if self.engine.transcriber is not None:
            self.engine.reload_model()
        if self.engine.writer is not None:
            self.engine.unload_writer()
            if self.config.writer_preload:
                self.engine.load_writer()

    def _on_close_action(self) -> None:
        self.config.close_action = self.close_var.get()
        self.config.save()

    def _on_fillers(self) -> None:
        self.config.remove_fillers = self.fillers_var.get()
        self.config.save()

    def _save_home(self) -> None:
        self.config.home_url = self.home_url_var.get().strip()
        self.config.home_key = self.home_key_var.get().strip()
        self.config.save()
        self.engine.check_home_now()

    def _on_home(self) -> None:
        self._save_home()
        self.config.home_enabled = self.home_var.get()
        self.config.save()
        self.engine.check_home_now()

    def _test_home(self) -> None:
        from voice_typer import home

        self._save_home()
        self.home_test_btn.state(["disabled"])
        self.home_test_info.configure(text=self.t("home_testing"))
        url, key = self.config.home_url, self.config.home_key

        def work():
            try:
                info = home.HomeClient(url, key).ping()
                msg = self.t("home_ok", whisper=info.get("whisper") or "?", writer=info.get("writer") or "-",
                             where=self.t("where_gpu" if info.get("device") == "cuda" else "where_cpu"))
                wd = info.get("writer_device")
                if wd and wd != "cuda":   # the slow case: its writing AI landed on the processor
                    msg += self.t("home_status_ai_cpu")
            except home.HomeError as exc:
                msg = self.t("home_fail", reason=self.t(f"home_err_{exc}"))

            def show():
                self.home_test_btn.state(["!disabled"])
                self.home_test_info.configure(text=msg)
            self.call_soon(show)

        threading.Thread(target=work, daemon=True).start()

    def _on_numbers(self) -> None:
        self.config.numbers_as_digits = self.numbers_var.get()
        self.config.save()

    def _on_mic_button(self) -> None:
        self.config.mic_button = self.micbtn_var.get()
        self.config.save()
        self.mic_button.sync()

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
