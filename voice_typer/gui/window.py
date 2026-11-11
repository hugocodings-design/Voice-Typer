"""Main window: sidebar navigation, status, tray and engine events. Pages are mixins in gui/pages/."""

import datetime as dt
import queue
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from voice_typer.gui import dialogs as messagebox

from voice_typer import gpu, languages, models, ui_theme
from voice_typer.app import Engine
from voice_typer.config import load_history, save_history
from voice_typer.gui.common import PAGES
from voice_typer.gui.pages.dictionary import DictionaryPage
from voice_typer.gui.pages.help import HelpPage
from voice_typer.gui.pages.home import HomePage
from voice_typer.gui.pages.languages import LanguagesPage
from voice_typer.gui.pages.models_page import ModelsPage
from voice_typer.gui.pages.remote_page import RemotePage
from voice_typer.gui.pages.settings import SettingsPage
from voice_typer.gui.pages.writing import WritingPage
from voice_typer.gui.shortcuts import ShortcutRecorder
from voice_typer.gui.updates import UpdatesMixin
from voice_typer.gui.wizard import WelcomeWizard
from voice_typer.i18n import pretty_hotkey, tr
from voice_typer.overlay import Overlay
from voice_typer.recorder import Recorder
from voice_typer.tray import Tray


class Window(HomePage, DictionaryPage, LanguagesPage, ModelsPage, SettingsPage, WritingPage,
             RemotePage, HelpPage, ShortcutRecorder, WelcomeWizard, UpdatesMixin):
    def __init__(self, engine: Engine):
        self.engine = engine
        self.config = engine.config
        self._calls: queue.Queue[Callable[[], None]] = queue.Queue()
        self._status = ("status_starting", "busy", True, {})
        self._last_info = None
        self._hint_shown = False
        self._rec_dialog: tk.Toplevel | None = None
        self._rec_token = 0
        self._page = "home"
        self.history: list[dict] = load_history()
        if self.history and not engine.last_text:
            engine.last_text = self.history[-1].get("text", "")
        self._cuda = gpu.cuda_available()
        self._gpu_name = gpu.gpu_name() if self._cuda else None
        self._mic_test: Recorder | None = None

        self.root = tk.Tk()
        self.root.title("Voice Typer")
        try:  # our microphone badge instead of Tk's feather, in the title bar and taskbar
            from PIL import ImageTk

            from voice_typer.tray import _icon_image

            self._app_icons = [ImageTk.PhotoImage(_icon_image(size=s)) for s in (64, 32, 16)]
            self.root.iconphoto(True, *self._app_icons)
        except Exception:  # noqa: BLE001
            pass
        self.root.geometry("1060x740")
        self.root.minsize(900, 640)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.fonts = ui_theme.Fonts(self.root)
        self.overlay = Overlay(self.root, lambda: self.engine.recorder.level)
        self.tray = Tray(self._tray_menu)
        self.tray.start()
        self._build()

    # ================================================================== helpers
    def t(self, key: str, **kw) -> str:
        return tr(self.config.ui_language, key, **kw)

    def lang_name(self, code: str | None) -> str:
        return languages.name(code, self.config.ui_language)

    def call_soon(self, fn: Callable[[], None]) -> None:
        """Thread-safe: run fn on the tkinter thread."""
        self._calls.put(fn)

    def _hotkey_label(self, combo: str | None = None) -> str:
        return pretty_hotkey(self.config.ui_language, combo if combo is not None else self.config.hotkey)

    def _card(self, parent, title: str | None = None, subtitle: str | None = None, *,
              col: int | None = None, wrap: int = 720, **pack) -> ttk.Frame:
        outer = ttk.Frame(parent, style="Card.TFrame", padding=(18, 14))
        if col is not None:  # equal-width columns inside a _columns() frame
            outer.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0), pady=(0, 12))
        else:
            outer.pack(fill=pack.pop("fill", "x"), expand=pack.pop("expand", False),
                       pady=pack.pop("pady", (0, 12)), **pack)
        if title:
            ttk.Label(outer, text=title, font=self.fonts.h2).pack(anchor="w")
        if subtitle:
            ttk.Label(outer, text=subtitle, style="Muted.TLabel", wraplength=wrap,
                      justify="left").pack(anchor="w", pady=(2, 0))
        if title or subtitle:
            ttk.Frame(outer, height=10).pack()
        return outer

    @staticmethod
    def _columns(parent, expand: bool = False) -> ttk.Frame:
        row = ttk.Frame(parent)
        row.pack(fill="both" if expand else "x", expand=expand)
        row.columnconfigure(0, weight=1, uniform="cols")
        row.columnconfigure(1, weight=1, uniform="cols")
        row.rowconfigure(0, weight=1)
        return row

    def _keycaps(self, parent, combo: str) -> tk.Frame:
        pal = self.pal
        row = tk.Frame(parent, bg=pal["card"])
        if not combo:
            tk.Label(row, text=self.t("none"), font=self.fonts.body, bg=pal["card"], fg=pal["muted"]).pack()
            return row
        names = pretty_hotkey(self.config.ui_language, combo).split(" + ")
        for i, n in enumerate(names):
            if i:
                tk.Label(row, text="+", font=self.fonts.body, bg=pal["card"], fg=pal["muted"]).pack(side="left", padx=4)
            cap = tk.Label(row, text=n, font=self.fonts.key, bg=pal["key_bg"], fg=pal["text"], padx=12, pady=5,
                           highlightthickness=1, highlightbackground=pal["key_border"])
            cap.pack(side="left")
        return row

    def _menu(self) -> tk.Menu:
        pal = self.pal
        return tk.Menu(self.root, tearoff=False, bg=pal["card"], fg=pal["text"], activebackground=pal["accent"],
                       activeforeground=pal["accent_fg"], bd=0, relief="flat", font=self.fonts.body)

    @staticmethod
    def _popup(menu: tk.Menu, event) -> None:
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    @staticmethod
    def _tree_row_at(tree: ttk.Treeview, event) -> str | None:
        iid = tree.identify_row(event.y)
        if iid:
            tree.selection_set(iid)
            tree.focus(iid)
        return iid or None

    # ================================================================== layout
    def _build(self) -> None:
        self._stop_mic_test()
        for child in self.root.winfo_children():
            if not isinstance(child, tk.Toplevel):  # keep the overlay, live caption and assistant windows
                child.destroy()
        self.mode, self.pal = ui_theme.apply(self.root, self.config.theme)
        pal = self.pal
        messagebox.configure(self.mode, pal, self.fonts, self.config.ui_language)  # themed pop-ups
        self.root.configure(bg=pal["bg"])

        side = tk.Frame(self.root, bg=pal["sidebar"], width=230)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=pal["sidebar"])
        brand.pack(fill="x", padx=18, pady=(22, 18))
        tk.Label(brand, text=ui_theme.ICONS["mic"], font=(self.fonts.icon[0], 18), bg=pal["sidebar"],
                 fg=pal["accent"]).pack(side="left")
        tk.Label(brand, text="Voice Typer", font=self.fonts.app, bg=pal["sidebar"], fg=pal["text"]).pack(
            side="left", padx=10)

        self.nav_items: dict[str, tuple] = {}
        for key, icon in PAGES:
            self._nav_item(side, key, icon)

        foot = tk.Frame(side, bg=pal["sidebar"])
        foot.pack(side="bottom", fill="x", padx=18, pady=16)
        self.side_status_dot = tk.Canvas(foot, width=10, height=10, highlightthickness=0, bg=pal["sidebar"])
        self.side_status_dot.pack(side="left")
        self.side_dot_id = self.side_status_dot.create_oval(1, 1, 9, 9, fill=pal["busy"], outline="")
        self.side_status = tk.Label(foot, text="", font=self.fonts.small, bg=pal["sidebar"], fg=pal["muted"],
                                    anchor="w", justify="left")
        self.side_status.pack(side="left", padx=8)

        self.content = ttk.Frame(self.root, padding=(30, 24, 30, 18))
        self.content.pack(side="left", fill="both", expand=True)
        self.pages: dict[str, ttk.Frame] = {}
        for key, _ in PAGES:
            frame = ttk.Frame(self.content)
            self.pages[key] = frame
            getattr(self, f"_page_{key}")(frame)
        self._show_page(self._page)
        self._upd_build_banner()
        self._render_status()
        self._render_last()
        self._render_home_language()
        if getattr(self, "_wizard", None) is not None:  # e.g. a shortcut changed from the assistant
            self._wizard_restyle()

    def _nav_item(self, side, key: str, icon: str) -> None:
        pal = self.pal
        row = tk.Frame(side, bg=pal["sidebar"], cursor="hand2")
        row.pack(fill="x", padx=10, pady=2)
        bar = tk.Frame(row, bg=pal["sidebar"], width=3, height=20)
        bar.pack(side="left", padx=(2, 8), pady=8)
        ic = tk.Label(row, text=ui_theme.ICONS[icon], font=self.fonts.icon, bg=pal["sidebar"], fg=pal["text"])
        ic.pack(side="left")
        lbl = tk.Label(row, text=self.t(f"nav_{key}"), font=self.fonts.nav, bg=pal["sidebar"], fg=pal["text"])
        lbl.pack(side="left", padx=12, pady=9)
        widgets = (row, bar, ic, lbl)
        self.nav_items[key] = widgets

        def enter(_e):
            if self._page != key:
                for w in (row, ic, lbl):
                    w.configure(bg=pal["hover"])
                bar.configure(bg=pal["hover"])

        def leave(_e):
            self._paint_nav(key)

        for w in widgets:
            w.bind("<Button-1>", lambda _e, k=key: self._show_page(k))
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)

    def _paint_nav(self, key: str) -> None:
        pal = self.pal
        row, bar, ic, lbl = self.nav_items[key]
        active = key == self._page
        bg = pal["accent_soft"] if active else pal["sidebar"]
        for w in (row, ic, lbl):
            w.configure(bg=bg)
        bar.configure(bg=pal["accent"] if active else bg)
        lbl.configure(font=self.fonts.bold if active else self.fonts.nav)
        ic.configure(fg=pal["accent"] if active else pal["text"])

    def _show_page(self, key: str) -> None:
        if key != "settings":
            self._stop_mic_test()
        self._page = key
        for k, frame in self.pages.items():
            frame.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k in self.nav_items:
            self._paint_nav(k)
        if key == "models":
            self._refresh_models()

    def _page_header(self, parent, key: str) -> None:
        ttk.Label(parent, text=self.t(f"title_{key}"), font=self.fonts.h1).pack(anchor="w")
        ttk.Label(parent, text=self.t(f"sub_{key}"), style="Muted.TLabel").pack(anchor="w", pady=(2, 18))

    # ================================================================== status
    def _set_status(self, key: str, color: str, busy: bool = False, **kw) -> None:
        self._status = (key, color, busy, kw)
        self._render_status()

    def _set_ready(self) -> None:
        key = "status_ready_toggle" if self.config.mode == "toggle" else "status_ready_hold"
        self._set_status(key, "ok")

    def _render_status(self) -> None:
        key, color, busy, kw = self._status
        text = self.t(key, **{**kw, "hotkey": self._hotkey_label()})
        self.status_var.set(text)
        self.dot.itemconfigure(self.dot_id, fill=self.pal[color])
        self.side_status_dot.itemconfigure(self.side_dot_id, fill=self.pal[color])
        self.side_status.configure(text=self.t(f"side_{color}"))
        if busy:
            self.progress.pack(side="right")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()
        self._render_chips()

    def _set_last(self, value) -> None:
        self._last_info = value
        self._render_last()

    def _render_last(self) -> None:
        if self._last_info is None:
            self.last_var.set(self.t("last_empty", hotkey=self._hotkey_label()))
        elif isinstance(self._last_info, tuple):
            key, kw = self._last_info
            self.last_var.set(self.t(key, **kw))
        else:
            self.last_var.set(self._last_info)

    # ================================================================== tray
    def _tray_menu(self, pystray):
        def lang_item(code):
            return pystray.MenuItem(
                self.lang_name(code),
                lambda: self.call_soon(lambda: self.engine.set_language(code)),
                checked=lambda _item: self.config.language == code, radio=True)

        lang_items = [lang_item(None)] + [lang_item(c) for c in self.config.favorite_languages]
        upd = []
        if self._update:
            upd = [pystray.MenuItem(self.t("upd_tray_item", version=self._update["version"]),
                                    lambda: self.call_soon(self._upd_install)), pystray.Menu.SEPARATOR]
        return pystray.Menu(
            *upd,
            pystray.MenuItem(self.t("tray_open"), lambda: self.call_soon(self._show_window), default=True),
            pystray.MenuItem(self.t("tray_language"), pystray.Menu(*lang_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("tray_quit"), lambda: self.call_soon(self._quit)),
        )

    # ================================================================== engine events
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

    def _overlay_lang(self) -> str:
        return languages.short(self.config.language)

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
                self._set_status("status_no_model", "off")
            messagebox.showerror(self.t("model_error_title"),
                                 self.t("model_error_msg", name=self._label_for(source), err=err),
                                 parent=self.root)
        elif kind == "recording":
            key = "status_recording_toggle" if self.config.mode == "toggle" else "status_recording_hold"
            self._set_status(key, "rec")
            if self.config.overlay:
                extra = f"  ·  {payload['name']}" if payload else ""
                self.overlay.show("recording", f"{self.t('overlay_listening')}  {self._overlay_lang()}{extra}")
            self.tray.set_recording(True)
        elif kind == "rewriting":
            self._set_status("status_rewriting", "busy", busy=True, name=payload["name"])
            if self.config.overlay:
                self.overlay.show("transcribing", self.t("overlay_rewriting", name=payload["name"]))
        elif kind in ("writer_loading", "writer_loaded", "writer_unloaded"):
            self._render_llm_status()
        elif kind == "writer_error":
            self._render_llm_status()
            self._set_last(self.t("wr_error", err=str(payload)[:300]))
            if self._page == "writing":
                messagebox.showerror(self.t("wr_load_error_title"), str(payload)[:500], parent=self.root)
        elif kind == "live":
            if self.config.overlay:
                self.overlay.set_live(payload)
        elif kind == "transcribing":
            self.overlay.hide_live()
            self._set_status("status_transcribing", "busy", busy=True)
            if self.config.overlay:
                self.overlay.show("transcribing", self.t("overlay_transcribing"))
            self.tray.set_recording(False)
        elif kind == "transcript":
            text, seconds, lang, preset_name, raw = payload
            self._set_ready()
            self.overlay.hide()
            tag = f"✎ {preset_name} — " if preset_name else ""
            self._set_last(f"{tag}« {text} »  ({seconds:.1f} s)" if text else ("nothing_heard", {}))
            if text and self.config.history_enabled:
                item = {"time": dt.datetime.now().isoformat(timespec="seconds"),
                        "text": text, "lang": lang, "secs": round(seconds, 2)}
                if preset_name:
                    item.update(preset=preset_name, raw=raw)
                self.history.append(item)
                self.history = self.history[-200:]
                save_history(self.history)
                self._refresh_history()
        elif kind == "idle":
            self._set_ready()
            self.overlay.hide()
            self.tray.set_recording(False)
            if payload == "too_short":
                self._set_last(("too_short", {}))
            elif payload:
                self._set_last(str(payload))
        elif kind == "cancelled":
            self._set_ready()
            self.tray.set_recording(False)
            self._set_last(("cancelled", {}))
            if self.config.overlay:
                self.overlay.flash(self.t("overlay_cancelled"))
            else:
                self.overlay.hide()
        elif kind == "rewrite_empty":
            self._set_last(("rw_empty", {}))
            if self.config.overlay:
                self.overlay.flash(self.t("rw_empty_short"), ms=2200)
        elif kind == "pasted_last":
            if self.config.overlay:
                self.overlay.flash(self.t("overlay_pasted"))
        elif kind in ("remote_status", "remote_changed", "remote_down", "host_error"):
            self._rm_on_event(kind, payload)
        elif kind == "status" and payload == "no_model":
            self._set_last(("no_model", {}))
        elif kind == "language_changed":
            self._render_home_language()
            self._refresh_languages()
            self.tray.refresh()
            if self.config.overlay:
                self.overlay.flash(f"{self.t('lang_now')} {self.lang_name(payload)}")

    # ================================================================== window lifecycle
    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self) -> None:
        self._stop_mic_test()
        if self.tray.available:
            self.root.withdraw()
            if not self._hint_shown:
                self._hint_shown = True
                self.tray.notify(self.t("tray_hint"))
        else:
            self._quit()

    def _quit(self) -> None:
        self._stop_mic_test()
        self.engine.stop()
        self.tray.stop()
        self.root.destroy()

    def run(self, start_hidden: bool = False, updated: bool = False) -> None:
        self.root.after(60, self._poll)
        self._upd_schedule()
        if updated:  # restarted by the installer after an automatic update
            from voice_typer import __version__, updater

            updater.cleanup()
            self.root.after(1500, lambda: self.tray.notify(self.t("upd_done", version=__version__)))
        if not self.config.first_run_done:
            # The assistant picks the models first; the engine starts when it closes.
            self.root.after(300, lambda: self._open_wizard(on_close=self.engine.start))
        else:
            if start_hidden and self.tray.available:
                self.root.withdraw()
            self.engine.start()
        self.root.mainloop()
