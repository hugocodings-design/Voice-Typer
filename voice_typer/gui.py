"""Desktop window: status, shortcut, language, model manager and settings (tkinter)."""

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import keyboard

from voice_typer import autostart, gpu, models
from voice_typer.app import Engine
from voice_typer.hotkey import validate as validate_hotkey
from voice_typer.i18n import GROUP_LABELS, MODEL_NOTES, pretty_hotkey, tr
from voice_typer.overlay import Overlay
from voice_typer.tray import Tray

COLORS = {"ready": "#2e9d4f", "recording": "#d93025", "busy": "#e8a317", "error": "#9e9e9e"}
UI_LANGUAGES = [("fr", "Français"), ("en", "English")]
PRESETS = ["f9", "right ctrl", "ctrl+windows", "ctrl+alt+space"]


class Window:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.config = engine.config
        self._calls: queue.Queue[Callable[[], None]] = queue.Queue()
        self._status = ("status_starting", "busy", True, {})
        self._last = None  # (key, kwargs) or raw text
        self._hint_shown = False
        self._rec_dialog: tk.Toplevel | None = None
        self._rec_token = 0

        self.root = tk.Tk()
        self.root.title("Voice Typer")
        self.root.geometry("960x680")
        self.root.minsize(720, 560)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=26)
        style.configure("Key.TLabel", font=("Segoe UI", 16, "bold"), padding=(14, 6),
                        background="#eef3fd", foreground="#174ea6")
        style.configure("Hint.TLabel", foreground="#666")
        style.configure("Status.TLabel", font=("Segoe UI", 12, "bold"))

        self._cuda = gpu.cuda_available()
        self._gpu_name = gpu.gpu_name() if self._cuda else None
        self.overlay = Overlay(self.root, lambda: self.engine.recorder.level)
        self.tray: Tray | None = None
        self._make_tray()
        self._build()

    # ---- helpers ------------------------------------------------------------------------
    def t(self, key: str, **kw) -> str:
        return tr(self.config.ui_language, key, **kw)

    def call_soon(self, fn: Callable[[], None]) -> None:
        """Thread-safe: run fn on the tkinter thread."""
        self._calls.put(fn)

    def _hotkey_label(self) -> str:
        return pretty_hotkey(self.config.ui_language, self.config.hotkey)

    def _make_tray(self) -> None:
        if self.tray:
            self.tray.stop()
        self.tray = Tray(
            {"open": self.t("tray_open"), "quit": self.t("tray_quit")},
            on_open=lambda: self.call_soon(self._show_window),
            on_quit=lambda: self.call_soon(self._quit),
        )
        self.tray.start()

    # ---- layout -------------------------------------------------------------------------
    def _build(self) -> None:
        for child in self.root.winfo_children():
            if child is not self.overlay.top:
                child.destroy()

        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=14, pady=(12, 4))
        self.dot = tk.Canvas(header, width=18, height=18, highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(2, 2, 16, 16, fill=COLORS["busy"], outline="")
        self.status_var = tk.StringVar()
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side="left", padx=8)
        self.progress = ttk.Progressbar(header, mode="indeterminate", length=140)

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        home, models_tab, settings = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(home, text=f"  {self.t('tab_home')}  ")
        nb.add(models_tab, text=f"  {self.t('tab_models')}  ")
        nb.add(settings, text=f"  {self.t('tab_settings')}  ")
        self._build_home(home)
        self._build_models(models_tab)
        self._build_settings(settings)

        self._render_status()
        self._render_last()
        self._refresh_models()

    def _build_home(self, tab: ttk.Frame) -> None:
        pad = {"padx": 10, "pady": 8}

        sc = ttk.LabelFrame(tab, text=self.t("shortcut_title"))
        sc.pack(fill="x", **pad)
        row = ttk.Frame(sc)
        row.pack(fill="x", padx=10, pady=(10, 4))
        self.key_label = ttk.Label(row, text=self._hotkey_label(), style="Key.TLabel")
        self.key_label.pack(side="left")
        ttk.Button(row, text=self.t("shortcut_change"), command=self._record_hotkey).pack(side="left", padx=12)
        self.mode_var = tk.StringVar(value=self.config.mode)
        for value, key in (("hold", "mode_hold"), ("toggle", "mode_toggle")):
            ttk.Radiobutton(sc, text=self.t(key), value=value, variable=self.mode_var,
                            command=self._on_mode).pack(anchor="w", padx=12, pady=2)
        ttk.Frame(sc, height=6).pack()

        lang = ttk.LabelFrame(tab, text=self.t("lang_title"))
        lang.pack(fill="x", **pad)
        self.lang_codes = [code for code, _ in models.LANGUAGES]
        names = [self.t("lang_auto") if code is None else name for code, name in models.LANGUAGES]
        self.lang_combo = ttk.Combobox(lang, state="readonly", width=30, values=names)
        current = self.config.language if self.config.language in self.lang_codes else None
        self.lang_combo.current(self.lang_codes.index(current))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)
        self.lang_combo.pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Label(lang, text=self.t("lang_hint"), style="Hint.TLabel").pack(anchor="w", padx=10, pady=(0, 10))

        last = ttk.LabelFrame(tab, text=self.t("last_title"))
        last.pack(fill="both", expand=True, **pad)
        self.last_var = tk.StringVar()
        ttk.Label(last, textvariable=self.last_var, wraplength=760, justify="left").pack(
            anchor="w", padx=10, pady=10, fill="x"
        )
        ttk.Button(last, text=self.t("copy"), command=self._copy_last).pack(anchor="e", padx=10, pady=(0, 10))

    def _build_models(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text=self.t("models_intro"), style="Hint.TLabel").pack(anchor="w", padx=12, pady=(10, 0))
        cols = ("size", "speed", "accuracy", "status", "note")
        self.tree = ttk.Treeview(tab, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=self.t("col_model"))
        self.tree.column("#0", width=230, stretch=False)
        self.tree.tag_configure("group", font=("Segoe UI", 9, "bold"), background="#eef3fd")
        for col, key, width in [("size", "col_size", 65), ("speed", "col_speed", 75),
                                ("accuracy", "col_accuracy", 75), ("status", "col_status", 110),
                                ("note", "col_notes", 300)]:
            self.tree.heading(col, text=self.t(key))
            self.tree.column(col, width=width, stretch=(col == "note"))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(6, 4))
        self.tree.bind("<Double-1>", lambda _e: self._use_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", padx=10, pady=(4, 10))
        self.use_btn = ttk.Button(buttons, text=self.t("btn_use"), command=self._use_selected)
        self.use_btn.pack(side="left")
        ttk.Button(buttons, text=self.t("btn_import_folder"), command=self._import_folder).pack(side="left", padx=6)
        ttk.Button(buttons, text=self.t("btn_import_hf"), command=self._import_hf).pack(side="left")
        self.remove_btn = ttk.Button(buttons, text=self.t("btn_remove"), command=self._remove_selected)
        self.remove_btn.pack(side="right")

    def _build_settings(self, tab: ttk.Frame) -> None:
        pad = {"padx": 10, "pady": 8}
        gen = ttk.LabelFrame(tab, text=self.t("set_general"))
        gen.pack(fill="x", **pad)
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(gen, text=self.t("set_autostart"), variable=self.autostart_var,
                        command=self._on_autostart).pack(anchor="w", padx=10, pady=(10, 4))
        self.overlay_var = tk.BooleanVar(value=self.config.overlay)
        ttk.Checkbutton(gen, text=self.t("set_overlay"), variable=self.overlay_var,
                        command=self._on_overlay).pack(anchor="w", padx=10, pady=(4, 10))

        acc = ttk.LabelFrame(tab, text=self.t("set_accel"))
        acc.pack(fill="x", **pad)
        self.device_var = tk.StringVar(value=self.config.device)
        for value, key in (("auto", "accel_auto"), ("cuda", "accel_cuda"), ("cpu", "accel_cpu")):
            ttk.Radiobutton(acc, text=self.t(key), value=value, variable=self.device_var,
                            command=self._on_device).pack(anchor="w", padx=10, pady=(6 if value == "auto" else 2, 2))
        self.accel_var = tk.StringVar()
        ttk.Label(acc, textvariable=self.accel_var, style="Hint.TLabel").pack(anchor="w", padx=10, pady=(4, 10))
        self._render_accel()

        out = ttk.LabelFrame(tab, text=self.t("set_output"))
        out.pack(fill="x", **pad)
        self.output_var = tk.StringVar(value=self.config.output)
        for value, key in (("paste", "out_paste"), ("type", "out_type")):
            ttk.Radiobutton(out, text=self.t(key), value=value, variable=self.output_var,
                            command=self._on_output).pack(anchor="w", padx=10, pady=4)

        ui = ttk.LabelFrame(tab, text=self.t("set_ui_lang"))
        ui.pack(fill="x", **pad)
        self.ui_combo = ttk.Combobox(ui, state="readonly", width=20, values=[n for _, n in UI_LANGUAGES])
        codes = [c for c, _ in UI_LANGUAGES]
        self.ui_combo.current(codes.index(self.config.ui_language) if self.config.ui_language in codes else 0)
        self.ui_combo.bind("<<ComboboxSelected>>", self._on_ui_language)
        self.ui_combo.pack(anchor="w", padx=10, pady=10)

        ttk.Button(tab, text=self.t("btn_quit"), command=self._quit).pack(anchor="e", padx=12, pady=12)

    # ---- status / last dictation ----------------------------------------------------------
    def _set_status(self, key: str, color: str, busy: bool = False, **kw) -> None:
        self._status = (key, color, busy, kw)
        self._render_status()

    def _set_ready(self) -> None:
        key = "status_ready_toggle" if self.config.mode == "toggle" else "status_ready_hold"
        self._set_status(key, "ready")

    def _render_status(self) -> None:
        key, color, busy, kw = self._status
        self.status_var.set(self.t(key, **{**kw, "hotkey": self._hotkey_label()}))
        self.dot.itemconfigure(self.dot_id, fill=COLORS[color])
        if busy:
            self.progress.pack(side="right")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _set_last(self, value) -> None:
        self._last = value
        self._render_last()

    def _render_last(self) -> None:
        if self._last is None:
            self.last_var.set(self.t("last_empty", hotkey=self._hotkey_label()))
        elif isinstance(self._last, tuple):
            key, kw = self._last
            self.last_var.set(self.t(key, **kw))
        else:
            self.last_var.set(self._last)

    def _copy_last(self) -> None:
        text = self.last_var.get()
        self.root.clipboard_clear()
        self.root.clipboard_append(text.split(")  ", 1)[-1] if text.startswith("(") else text)

    # ---- models ---------------------------------------------------------------------------
    def _label_for(self, source: str) -> str:
        for m in models.all_models(self.config.custom_models):
            if m.source == source:
                return m.label
        return source

    def _note_for(self, m: models.ModelInfo) -> str:
        if m.custom:
            return self.t("imported_model")
        return MODEL_NOTES.get(self.config.ui_language, MODEL_NOTES["en"]).get(m.source, m.note)

    def _refresh_models(self) -> None:
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        active = self.engine.transcriber.source if self.engine.transcriber else None
        all_m = models.all_models(self.config.custom_models)
        labels = GROUP_LABELS.get(self.config.ui_language, GROUP_LABELS["en"])
        for group in models.GROUPS:
            members = [m for m in all_m if m.group == group]
            if not members:
                continue
            gid = f"group:{group}"
            self.tree.insert("", "end", iid=gid, text=labels[group], open=True, tags=("group",))
            for m in members:
                if m.source == self.engine.loading_source:
                    status = self.t("st_loading")
                elif m.source == active:
                    status = self.t("st_in_use")
                elif models.is_downloaded(m.source):
                    status = self.t("st_downloaded")
                else:
                    status = self.t("st_not_downloaded")
                self.tree.insert(gid, "end", iid=m.source, text=m.label,
                                 values=(m.size, m.speed, m.accuracy, status, self._note_for(m)))
        keep = [s for s in selected if self.tree.exists(s)]
        if keep:
            self.tree.selection_set(keep)
        elif active and self.tree.exists(active):
            self.tree.selection_set(active)
        self._update_buttons()

    def _selected(self) -> models.ModelInfo | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return next((m for m in models.all_models(self.config.custom_models) if m.source == sel[0]), None)

    def _update_buttons(self) -> None:
        m = self._selected()
        active = self.engine.transcriber.source if self.engine.transcriber else None
        busy = self.engine.loading_source is not None
        self.use_btn.state(["!disabled"] if m and not busy and m.source != active else ["disabled"])
        self.remove_btn.state(["!disabled"] if m and m.custom and m.source != active else ["disabled"])

    def _use_selected(self) -> None:
        m = self._selected()
        if m is None or self.engine.loading_source is not None:
            return
        if not models.is_downloaded(m.source):
            size = f" ({m.size})" if m.size else ""
            if not messagebox.askyesno(self.t("dl_title"), self.t("dl_msg", name=m.label, size=size),
                                       parent=self.root):
                return
        self.engine.load_model(m.source)

    def _add_custom(self, label: str, source: str) -> None:
        if any(m.source == source for m in models.all_models(self.config.custom_models)):
            messagebox.showinfo(self.t("already_added_title"), self.t("already_added_msg", name=label),
                                parent=self.root)
            return
        self.config.custom_models.append({"label": label, "source": source})
        self.config.save()
        self._refresh_models()
        self.tree.selection_set(source)
        self.tree.see(source)

    def _import_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title=self.t("folder_title"))
        if not folder:
            return
        missing = models.missing_model_files(folder)
        if missing:
            messagebox.showerror(self.t("folder_error_title"), self.t("folder_error_msg", missing=missing),
                                 parent=self.root)
            return
        self._add_custom(Path(folder).name, str(Path(folder)))

    def _import_hf(self) -> None:
        repo = simpledialog.askstring(self.t("hf_title"), self.t("hf_prompt"), parent=self.root)
        if not repo:
            return
        repo = repo.strip().removeprefix("https://huggingface.co/").strip("/")
        if repo.count("/") != 1:
            messagebox.showerror(self.t("hf_invalid_title"), self.t("hf_invalid_msg"), parent=self.root)
            return
        try:
            source = models.hf_source_for(repo)
        except Exception as exc:  # noqa: BLE001 — offline, typo, private repo…
            messagebox.showerror(self.t("hf_title"), self.t("hf_network", err=exc), parent=self.root)
            return
        if source is None:
            messagebox.showerror(self.t("hf_title"), self.t("hf_not_ct2"), parent=self.root)
            return
        self._add_custom(repo.split("/")[1], source)

    def _remove_selected(self) -> None:
        m = self._selected()
        if m is None or not m.custom:
            return
        if not messagebox.askyesno(self.t("remove_title"), self.t("remove_msg", name=m.label), parent=self.root):
            return
        self.config.custom_models = [c for c in self.config.custom_models if c["source"] != m.source]
        self.config.save()
        self._refresh_models()

    # ---- settings -------------------------------------------------------------------------
    def _on_language(self, _event=None) -> None:
        self.config.language = self.lang_codes[self.lang_combo.current()]
        self.config.save()

    def _on_mode(self) -> None:
        self.config.mode = self.mode_var.get()
        self.config.save()
        if not self.engine.recorder.is_recording and self._status[1] == "ready":
            self._set_ready()

    def _on_overlay(self) -> None:
        self.config.overlay = self.overlay_var.get()
        self.config.save()
        if not self.config.overlay:
            self.overlay.hide()

    def _render_accel(self) -> None:
        tr_ = self.engine.transcriber
        if tr_ is not None and tr_.device == "cuda":
            self.accel_var.set(self.t("accel_now_gpu", name=self._gpu_name or "NVIDIA"))
        elif tr_ is not None:
            no_gpu = self.config.device != "cpu" and not self._cuda
            self.accel_var.set(self.t("accel_now_cpu") + ("  —  " + self.t("accel_no_gpu") if no_gpu else ""))
        else:
            self.accel_var.set("")

    def _on_device(self) -> None:
        if self.device_var.get() == self.config.device:
            return
        self.config.device = self.device_var.get()
        self.config.save()
        self.engine.reload_model()

    def _on_output(self) -> None:
        self.config.output = self.output_var.get()
        self.config.save()

    def _on_autostart(self) -> None:
        try:
            autostart.set_enabled(self.autostart_var.get())
        except OSError as exc:
            self.autostart_var.set(autostart.is_enabled())
            messagebox.showerror("Voice Typer", str(exc), parent=self.root)

    def _on_ui_language(self, _event=None) -> None:
        self.config.ui_language = UI_LANGUAGES[self.ui_combo.current()][0]
        self.config.save()
        self._make_tray()
        self._build()

    # ---- shortcut recording ---------------------------------------------------------------
    def _record_hotkey(self) -> None:
        if self._rec_dialog is not None:
            return
        self.engine.pause_hotkey()
        dlg = self._rec_dialog = tk.Toplevel(self.root)
        dlg.title(self.t("rec_title"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.protocol("WM_DELETE_WINDOW", self._close_recorder)
        ttk.Label(dlg, text=self.t("rec_prompt"), justify="center").pack(padx=24, pady=(18, 8))
        ttk.Label(dlg, text=self.t("rec_waiting"), style="Key.TLabel").pack(padx=24, pady=8)
        ttk.Label(dlg, text=self.t("rec_presets"), style="Hint.TLabel").pack(pady=(10, 4))
        row = ttk.Frame(dlg)
        row.pack(padx=16, pady=(0, 8))
        for combo in PRESETS:
            ttk.Button(row, text=pretty_hotkey(self.config.ui_language, combo),
                       command=lambda c=combo: self._apply_hotkey(c)).pack(side="left", padx=4)
        ttk.Button(dlg, text=self.t("rec_cancel"), command=self._close_recorder).pack(pady=(4, 16))
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_reqheight()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
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
        if error:
            key = "rec_err_unknown" if error == "unknown" else "rec_err_single"
            messagebox.showerror(self.t("rec_err_title"),
                                 self.t(key, combo=pretty_hotkey(self.config.ui_language, combo)),
                                 parent=self._rec_dialog)
            self._listen_for_hotkey()
            return
        self._apply_hotkey(combo)

    def _apply_hotkey(self, combo: str) -> None:
        self.engine.set_hotkey(combo)
        self._close_recorder()
        self.key_label.configure(text=self._hotkey_label())
        self._render_status()
        self._render_last()

    def _close_recorder(self) -> None:
        self._rec_token += 1
        if self._rec_dialog is not None:
            self._rec_dialog.grab_release()
            self._rec_dialog.destroy()
            self._rec_dialog = None
        self.engine.resume_hotkey()

    # ---- engine events --------------------------------------------------------------------
    def _poll(self) -> None:
        while True:
            try:
                self._calls.get_nowait()()
            except queue.Empty:
                break
        while True:
            try:
                kind, payload = self.engine.events.get_nowait()
            except queue.Empty:
                break
            self._handle(kind, payload)
        self.root.after(60, self._poll)

    def _handle(self, kind: str, payload) -> None:
        if kind == "model_loading":
            key = "status_loading" if models.is_downloaded(payload) else "status_downloading"
            self._set_status(key, "busy", busy=True, name=self._label_for(payload))
            self._refresh_models()
        elif kind == "model_loaded":
            source, seconds = payload
            self._set_ready()
            on_gpu = self.engine.transcriber is not None and self.engine.transcriber.device == "cuda"
            self._set_last(("model_ready", {"name": self._label_for(source), "s": seconds,
                                            "where": self.t("where_gpu" if on_gpu else "where_cpu")}))
            self._refresh_models()
            self._render_accel()
        elif kind == "gpu_fallback":
            self._render_accel()
            if self.config.device == "cuda" or self._cuda:
                messagebox.showwarning(self.t("gpu_fallback_title"),
                                       self.t("gpu_fallback_msg", err=str(payload)[:400]), parent=self.root)
        elif kind == "model_error":
            source, err = payload
            self._refresh_models()
            if self.engine.transcriber:
                self._set_ready()
            else:
                self._set_status("status_no_model", "error")
            messagebox.showerror(self.t("model_error_title"),
                                 self.t("model_error_msg", name=self._label_for(source), err=err),
                                 parent=self.root)
        elif kind == "recording":
            key = "status_recording_toggle" if self.config.mode == "toggle" else "status_recording_hold"
            self._set_status(key, "recording")
            if self.config.overlay:
                self.overlay.show("recording", self.t("overlay_listening"))
            if self.tray:
                self.tray.set_recording(True)
        elif kind == "transcribing":
            self._set_status("status_transcribing", "busy", busy=True)
            if self.config.overlay:
                self.overlay.show("transcribing", self.t("overlay_transcribing"))
            if self.tray:
                self.tray.set_recording(False)
        elif kind == "transcript":
            text, seconds = payload
            self._set_ready()
            self.overlay.hide()
            self._set_last(f"({seconds:.1f} s)  {text}" if text else ("nothing_heard", {}))
        elif kind == "idle":
            self._set_ready()
            self.overlay.hide()
            if self.tray:
                self.tray.set_recording(False)
            if payload == "too_short":
                self._set_last(("too_short", {}))
            elif payload:
                self._set_last(str(payload))
        elif kind == "status" and payload == "no_model":
            self._set_last(("no_model", {}))

    # ---- window lifecycle -----------------------------------------------------------------
    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self) -> None:
        if self.tray and self.tray.available:
            self.root.withdraw()
            if not self._hint_shown:
                self._hint_shown = True
                self.tray.notify(self.t("tray_hint"))
        else:
            self._quit()

    def _quit(self) -> None:
        self.engine.stop()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def run(self, start_hidden: bool = False) -> None:
        if start_hidden and self.tray and self.tray.available:
            self.root.withdraw()
        self.engine.start()
        self.root.after(60, self._poll)
        self.root.mainloop()
