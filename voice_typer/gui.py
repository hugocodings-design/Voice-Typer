"""Desktop window: sidebar navigation + pages (Accueil, Dictionnaire, Langues, Modèles IA, Réglages)."""

import datetime as dt
import os
import queue
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import keyboard

from voice_typer import __version__, autostart, gpu, languages, models, ui_theme, writer
from voice_typer.app import Engine
from voice_typer.config import SETTINGS_DIR, load_history, save_history
from voice_typer.hotkey import normalize as normalize_hotkey
from voice_typer.hotkey import validate as validate_hotkey
from voice_typer.i18n import GROUP_LABELS, MODEL_NOTES, pretty_hotkey, tr
from voice_typer.overlay import Overlay
from voice_typer.recorder import Recorder, list_microphones
from voice_typer.tray import Tray

UI_LANGUAGES = [("fr", "Français"), ("en", "English")]
THEMES = ["system", "light", "dark"]
PRESETS = ["f9", "right ctrl", "ctrl+windows", "ctrl+alt+space"]
LANG_PRESETS = ["f8", "ctrl+alt+l", "ctrl+shift+l"]
PAGES = [("home", "home"), ("dictionary", "dictionary"), ("languages", "language"),
         ("models", "models"), ("writing", "writing"), ("settings", "settings")]
PASTE_PRESETS = ["f9", "f10", "ctrl+shift+v", "insert"]
WRITING_PRESET_KEYS =["f2", "f3", "f4", "f6", "f7", "ctrl+alt+e"]


class ScrollFrame(ttk.Frame):
    """Vertically scrollable container (mouse wheel works anywhere over it)."""

    def __init__(self, master, bg: str):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=bg, bd=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event) -> None:
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        while widget is not None:
            if widget is self:
                self.canvas.yview_scroll(int(-event.delta / 120), "units")
                return
            widget = widget.master


class Window:
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
            if child is not self.overlay.top:
                child.destroy()
        self.mode, self.pal = ui_theme.apply(self.root, self.config.theme)
        pal = self.pal
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
        self._render_status()
        self._render_last()
        self._render_home_language()

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

    # ================================================================== page: home
    def _page_home(self, page: ttk.Frame) -> None:
        pal = self.pal
        self._page_header(page, "home")

        hero = self._card(page)
        top = ttk.Frame(hero)
        top.pack(fill="x")
        self.dot = tk.Canvas(top, width=16, height=16, highlightthickness=0, bg=pal["card"])
        self.dot.pack(side="left", padx=(0, 10))
        self.dot_id = self.dot.create_oval(2, 2, 14, 14, fill=pal["busy"], outline="")
        self.status_var = tk.StringVar()
        ttk.Label(top, textvariable=self.status_var, font=self.fonts.status).pack(side="left")
        self.progress = ttk.Progressbar(top, mode="indeterminate", length=160)
        self.chips_var = tk.StringVar()
        ttk.Label(hero, textvariable=self.chips_var, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.last_var = tk.StringVar()
        ttk.Label(hero, textvariable=self.last_var, wraplength=720, justify="left").pack(anchor="w", pady=(6, 0))

        row = self._columns(page)
        lang = self._card(row, self.t("home_lang_title"), self.t("home_lang_sub"), col=0, wrap=330)
        self.lang_buttons = ttk.Frame(lang)
        self.lang_buttons.pack(anchor="w", fill="x")
        ttk.Button(lang, text=self.t("manage_languages"), style="TButton",
                   command=lambda: self._show_page("languages")).pack(anchor="w", pady=(10, 0))

        sc = self._card(row, self.t("shortcut_title"), col=1)
        caps_row = ttk.Frame(sc)
        caps_row.pack(fill="x")
        self._keycaps(caps_row, self.config.hotkey).pack(side="left")
        ttk.Button(caps_row, text=self.t("change"), command=lambda: self._record_hotkey("main")).pack(
            side="right")
        self.mode_var = tk.StringVar(value=self.config.mode)
        for value, key in (("hold", "mode_hold"), ("toggle", "mode_toggle")):
            ttk.Radiobutton(sc, text=self.t(key), value=value, variable=self.mode_var,
                            command=self._on_mode).pack(anchor="w", pady=(8 if value == "hold" else 2, 0))
        ttk.Label(sc, text=self.t("paste_last_title"), wraplength=330, justify="left").pack(anchor="w", pady=(12, 4))
        prow = ttk.Frame(sc)
        prow.pack(fill="x")
        self._keycaps(prow, self.config.paste_last_hotkey).pack(side="left")
        if self.config.paste_last_hotkey:
            ttk.Button(prow, text=self.t("wr_remove_key"),
                       command=lambda: self._set_paste_hotkey("")).pack(side="right", padx=(6, 0))
        ttk.Button(prow, text=self.t("change"), command=lambda: self._record_hotkey("paste")).pack(side="right")
        self.home_presets_var = tk.StringVar()
        presets_lbl = ttk.Label(sc, textvariable=self.home_presets_var, style="Muted.TLabel", wraplength=330,
                                justify="left", cursor="hand2")
        presets_lbl.pack(anchor="w", pady=(8, 0))
        presets_lbl.bind("<Button-1>", lambda _e: self._show_page("writing"))
        self._render_home_presets()

        hist = self._card(page, self.t("history_title"), fill="both", expand=True)
        wrap = ttk.Frame(hist)
        wrap.pack(fill="both", expand=True)
        self.hist_tree = ttk.Treeview(wrap, columns=("time", "lang", "text"), show="headings", height=5)
        for col, key, width, stretch in (("time", "col_time", 110, False), ("lang", "col_lang", 70, False),
                                         ("text", "col_text", 400, True)):
            self.hist_tree.heading(col, text=self.t(key), anchor="w")
            self.hist_tree.column(col, width=width, stretch=stretch, anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=sb.set)
        self.hist_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.hist_tree.bind("<Button-3>", self._history_menu)
        self.hist_tree.bind("<Double-1>", lambda _e: self._history_copy())
        self.hist_empty = ttk.Label(hist, style="Muted.TLabel")
        self._refresh_history()

    def _render_home_language(self) -> None:
        if not hasattr(self, "lang_buttons"):
            return
        for w in self.lang_buttons.winfo_children():
            w.destroy()
        options = [None] + [c for c in self.config.favorite_languages]
        for code in options:
            selected = code == self.config.language
            ttk.Button(self.lang_buttons, text=("✓ " if selected else "") + self.lang_name(code),
                       style="Accent.TButton" if selected else "TButton",
                       command=lambda c=code: self.engine.set_language(c)).pack(side="left", padx=(0, 6), pady=2)
        self._render_chips()

    def _render_chips(self) -> None:
        if not hasattr(self, "chips_var"):
            return
        tr_ = self.engine.transcriber
        parts = []
        if tr_:
            parts.append(f"{self.t('chip_model')} : {self._label_for(tr_.source)}")
            parts.append(self.t("chip_gpu") if tr_.device == "cuda" else self.t("chip_cpu"))
        parts.append(f"{self.t('chip_lang')} : {self.lang_name(self.config.language)}")
        if self.config.vocabulary:
            parts.append(self.t("chip_dict", n=len(self.config.vocabulary)))
        self.chips_var.set("   ·   ".join(parts))

    # ---- history
    def _refresh_history(self) -> None:
        if not hasattr(self, "hist_tree"):
            return
        self.hist_tree.delete(*self.hist_tree.get_children())
        for i, item in enumerate(reversed(self.history)):
            idx = len(self.history) - 1 - i
            try:
                when = dt.datetime.fromisoformat(item["time"]).strftime("%d/%m %H:%M")
            except (KeyError, ValueError):
                when = ""
            text = item.get("text", "").replace("\n", "  ")
            if item.get("preset"):
                text = f"✎ {item['preset']} — {text}"
            self.hist_tree.insert("", "end", iid=str(idx),
                                  values=(when, languages.short(item.get("lang")), text))
        if not self.history:
            self.hist_empty.configure(text=self.t("history_empty") if self.config.history_enabled
                                      else self.t("history_off"))
            self.hist_empty.pack(anchor="w", pady=(8, 0))
        else:
            self.hist_empty.pack_forget()

    def _history_selected(self) -> dict | None:
        sel = self.hist_tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        return self.history[idx] if 0 <= idx < len(self.history) else None

    def _history_copy(self) -> None:
        item = self._history_selected()
        if item:
            self.root.clipboard_clear()
            self.root.clipboard_append(item.get("text", ""))

    def _history_delete(self) -> None:
        sel = self.hist_tree.selection()
        if sel:
            del self.history[int(sel[0])]
            save_history(self.history)
            self._refresh_history()

    def _history_clear(self) -> None:
        if self.history and messagebox.askyesno(self.t("history_clear"), self.t("history_clear_confirm"),
                                                parent=self.root):
            self.history = []
            save_history(self.history)
            self._refresh_history()

    def _history_add_to_dict(self) -> None:
        item = self._history_selected()
        if item:
            self._show_page("dictionary")
            self.repl_from.delete(0, "end")
            self.repl_from.insert(0, item.get("text", ""))
            self.repl_to.focus_set()

    def _history_menu(self, event) -> None:
        if not self._tree_row_at(self.hist_tree, event):
            return
        m = self._menu()
        m.add_command(label=self.t("copy"), command=self._history_copy)
        raw = (self._history_selected() or {}).get("raw")
        if raw:
            m.add_command(label=self.t("hist_copy_raw"),
                          command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(raw)))
        m.add_command(label=self.t("hist_to_dict"), command=self._history_add_to_dict)
        m.add_separator()
        m.add_command(label=self.t("delete"), command=self._history_delete)
        m.add_command(label=self.t("history_clear"), command=self._history_clear)
        self._popup(m, event)

    # ================================================================== page: dictionary
    def _page_dictionary(self, page: ttk.Frame) -> None:
        self._page_header(page, "dictionary")
        cols = self._columns(page, expand=True)
        left = self._card(cols, self.t("vocab_title"), self.t("vocab_sub"), col=0, wrap=330)
        add = ttk.Frame(left)
        add.pack(fill="x")
        self.vocab_entry = ttk.Entry(add)
        self.vocab_entry.pack(side="left", fill="x", expand=True)
        self.vocab_entry.bind("<Return>", lambda _e: self._vocab_add())
        ttk.Button(add, text=self.t("add"), style="Accent.TButton", command=self._vocab_add).pack(
            side="left", padx=(8, 0))
        self.vocab_tree = ttk.Treeview(left, columns=("term",), show="headings")
        self.vocab_tree.heading("term", text=self.t("col_term"), anchor="w")
        self.vocab_tree.pack(fill="both", expand=True, pady=(10, 0))
        self.vocab_tree.bind("<Button-3>", self._vocab_menu)
        self.vocab_tree.bind("<Delete>", lambda _e: self._vocab_delete())
        self.vocab_tree.bind("<Double-1>", lambda _e: self._vocab_edit())

        right = self._card(cols, self.t("repl_title"), self.t("repl_sub"), col=1, wrap=330)
        form = ttk.Frame(right)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(2, weight=1)
        ttk.Label(form, text=self.t("repl_from"), style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text=self.t("repl_to"), style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.repl_from = ttk.Entry(form)
        self.repl_from.grid(row=1, column=0, sticky="ew")
        ttk.Label(form, text="→").grid(row=1, column=1, padx=6)
        self.repl_to = ttk.Entry(form)
        self.repl_to.grid(row=1, column=2, sticky="ew")
        self.repl_to.bind("<Return>", lambda _e: self._repl_add())
        ttk.Button(form, text=self.t("add"), style="Accent.TButton", command=self._repl_add).grid(
            row=1, column=3, padx=(8, 0))
        self.repl_tree = ttk.Treeview(right, columns=("from", "to"), show="headings")
        self.repl_tree.heading("from", text=self.t("repl_from"), anchor="w")
        self.repl_tree.heading("to", text=self.t("repl_to"), anchor="w")
        self.repl_tree.pack(fill="both", expand=True, pady=(10, 0))
        self.repl_tree.bind("<Button-3>", self._repl_menu)
        self.repl_tree.bind("<Delete>", lambda _e: self._repl_delete())
        self.repl_tree.bind("<Double-1>", lambda _e: self._repl_edit())
        ttk.Label(page, text=self.t("dict_tip"), style="Muted.TLabel", wraplength=740,
                  justify="left").pack(anchor="w", pady=(4, 0))
        self._refresh_dictionary()

    def _refresh_dictionary(self) -> None:
        self.vocab_tree.delete(*self.vocab_tree.get_children())
        for i, term in enumerate(self.config.vocabulary):
            self.vocab_tree.insert("", "end", iid=str(i), values=(term,))
        self.repl_tree.delete(*self.repl_tree.get_children())
        for i, rule in enumerate(self.config.replacements):
            self.repl_tree.insert("", "end", iid=str(i), values=(rule.get("from", ""), rule.get("to", "")))
        self._render_chips()

    def _vocab_add(self) -> None:
        term = self.vocab_entry.get().strip()
        if term and term.lower() not in (t.lower() for t in self.config.vocabulary):
            self.config.vocabulary.append(term)
            self.config.save()
            self._refresh_dictionary()
        self.vocab_entry.delete(0, "end")

    def _vocab_index(self) -> int | None:
        sel = self.vocab_tree.selection()
        return int(sel[0]) if sel else None

    def _vocab_edit(self) -> None:
        i = self._vocab_index()
        if i is None:
            return
        new = simpledialog.askstring(self.t("edit"), self.t("col_term"), initialvalue=self.config.vocabulary[i],
                                     parent=self.root)
        if new and new.strip():
            self.config.vocabulary[i] = new.strip()
            self.config.save()
            self._refresh_dictionary()

    def _vocab_delete(self) -> None:
        i = self._vocab_index()
        if i is not None:
            del self.config.vocabulary[i]
            self.config.save()
            self._refresh_dictionary()

    def _vocab_menu(self, event) -> None:
        if not self._tree_row_at(self.vocab_tree, event):
            return
        m = self._menu()
        m.add_command(label=self.t("edit"), command=self._vocab_edit)
        m.add_command(label=self.t("delete"), command=self._vocab_delete)
        self._popup(m, event)

    def _repl_add(self) -> None:
        src, dst = self.repl_from.get().strip(), self.repl_to.get().strip()
        if not src:
            return
        self.config.replacements = [r for r in self.config.replacements if r.get("from", "").lower() != src.lower()]
        self.config.replacements.append({"from": src, "to": dst})
        self.config.save()
        self.repl_from.delete(0, "end")
        self.repl_to.delete(0, "end")
        self.repl_from.focus_set()
        self._refresh_dictionary()

    def _repl_index(self) -> int | None:
        sel = self.repl_tree.selection()
        return int(sel[0]) if sel else None

    def _repl_edit(self) -> None:
        i = self._repl_index()
        if i is None:
            return
        rule = self.config.replacements.pop(i)
        self.config.save()
        self._refresh_dictionary()
        self.repl_from.delete(0, "end")
        self.repl_from.insert(0, rule.get("from", ""))
        self.repl_to.delete(0, "end")
        self.repl_to.insert(0, rule.get("to", ""))
        self.repl_to.focus_set()

    def _repl_delete(self) -> None:
        i = self._repl_index()
        if i is not None:
            del self.config.replacements[i]
            self.config.save()
            self._refresh_dictionary()

    def _repl_menu(self, event) -> None:
        if not self._tree_row_at(self.repl_tree, event):
            return
        m = self._menu()
        m.add_command(label=self.t("edit"), command=self._repl_edit)
        m.add_command(label=self.t("delete"), command=self._repl_delete)
        self._popup(m, event)

    # ================================================================== page: languages
    def _page_languages(self, page: ttk.Frame) -> None:
        self._page_header(page, "languages")
        top = ttk.Frame(page)
        top.pack(fill="x")
        hk = self._card(top, self.t("lang_hotkey_title"), self.t("lang_hotkey_sub"), side="left", fill="both",
                        expand=True)
        r = ttk.Frame(hk)
        r.pack(fill="x")
        self._keycaps(r, self.config.language_hotkey).pack(side="left")
        if self.config.language_hotkey:
            ttk.Button(r, text=self.t("disable"), command=lambda: self._set_lang_hotkey("")).pack(side="right")
        ttk.Button(r, text=self.t("change"), command=lambda: self._record_hotkey("lang")).pack(
            side="right", padx=6)

        card = self._card(page, self.t("all_languages"), self.t("all_languages_sub"), fill="both", expand=True)
        search_row = ttk.Frame(card)
        search_row.pack(fill="x")
        self.lang_search = tk.StringVar()
        entry = ttk.Entry(search_row, textvariable=self.lang_search)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Label(search_row, text=ui_theme.ICONS["language"], font=self.fonts.icon_small).pack(side="left", padx=8)
        self.lang_search.trace_add("write", lambda *_: self._refresh_languages())
        wrap = ttk.Frame(card)
        wrap.pack(fill="both", expand=True, pady=(10, 0))
        self.lang_tree = ttk.Treeview(wrap, columns=("fav", "name", "code", "active"), show="headings")
        for col, key, width, stretch in (("fav", "col_fav", 60, False), ("name", "col_language", 260, True),
                                         ("code", "col_code", 80, False), ("active", "col_active", 140, False)):
            self.lang_tree.heading(col, text=self.t(key), anchor="w")
            self.lang_tree.column(col, width=width, stretch=stretch, anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.lang_tree.yview)
        self.lang_tree.configure(yscrollcommand=sb.set)
        self.lang_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.lang_tree.bind("<Button-3>", self._languages_menu)
        self.lang_tree.bind("<Double-1>", lambda _e: self._toggle_favorite())
        self._refresh_languages()

    def _refresh_languages(self) -> None:
        if not hasattr(self, "lang_tree"):
            return
        query = self.lang_search.get().strip().lower() if hasattr(self, "lang_search") else ""
        favs = self.config.favorite_languages
        rows = [(c, self.lang_name(c)) for c, _fr, _en in languages.LANGUAGES]
        rows.sort(key=lambda r: (r[0] not in favs, favs.index(r[0]) if r[0] in favs else 0, r[1].lower()))
        self.lang_tree.delete(*self.lang_tree.get_children())
        auto_active = self.config.language is None
        if not query or query in self.lang_name(None).lower():
            self.lang_tree.insert("", "end", iid="__auto__",
                                  values=("", self.lang_name(None), "auto", self.t("active") if auto_active else ""))
        for code, nm in rows:
            if query and query not in nm.lower() and query not in code:
                continue
            self.lang_tree.insert("", "end", iid=code, values=(
                "★" if code in favs else "☆", nm, code, self.t("active") if code == self.config.language else ""))

    def _selected_language(self) -> str | None | bool:
        sel = self.lang_tree.selection()
        if not sel:
            return False
        return None if sel[0] == "__auto__" else sel[0]

    def _toggle_favorite(self, code=False) -> None:
        if code is False:
            code = self._selected_language()
        if code is False or code is None:
            return
        favs = self.config.favorite_languages
        if code in favs:
            favs.remove(code)
        else:
            favs.append(code)
        self.config.save()
        self._after_languages_changed()

    def _move_favorite(self, code: str, delta: int) -> None:
        favs = self.config.favorite_languages
        i = favs.index(code)
        j = max(0, min(len(favs) - 1, i + delta))
        favs.insert(j, favs.pop(i))
        self.config.save()
        self._after_languages_changed()

    def _after_languages_changed(self) -> None:
        sel = self.lang_tree.selection()
        self._refresh_languages()
        if sel and self.lang_tree.exists(sel[0]):
            self.lang_tree.selection_set(sel[0])
            self.lang_tree.see(sel[0])
        self._render_home_language()
        self.tray.refresh()

    def _languages_menu(self, event) -> None:
        if not self._tree_row_at(self.lang_tree, event):
            return
        code = self._selected_language()
        favs = self.config.favorite_languages
        m = self._menu()
        m.add_command(label=self.t("use_now"), command=lambda: self.engine.set_language(code))
        if code is not None:
            m.add_separator()
            if code in favs:
                m.add_command(label=self.t("fav_remove"), command=lambda: self._toggle_favorite(code))
                m.add_command(label=self.t("move_up"), command=lambda: self._move_favorite(code, -1),
                              state="normal" if favs.index(code) > 0 else "disabled")
                m.add_command(label=self.t("move_down"), command=lambda: self._move_favorite(code, 1),
                              state="normal" if favs.index(code) < len(favs) - 1 else "disabled")
            else:
                m.add_command(label=self.t("fav_add"), command=lambda: self._toggle_favorite(code))
        self._popup(m, event)

    # ================================================================== page: models
    def _page_models(self, page: ttk.Frame) -> None:
        self._page_header(page, "models")
        card = self._card(page, fill="both", expand=True)
        wrap = ttk.Frame(card)
        wrap.pack(fill="both", expand=True)
        cols = ("size", "speed", "accuracy", "status", "note")
        self.tree = ttk.Treeview(wrap, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text=self.t("col_model"), anchor="w")
        self.tree.column("#0", width=250, minwidth=200, stretch=False)
        self.tree.tag_configure("group", font=self.fonts.bold, background=self.pal["group_bg"])
        for col, key, width in [("size", "col_size", 62), ("speed", "col_speed", 76),
                                ("accuracy", "col_accuracy", 76), ("status", "col_status", 112),
                                ("note", "col_notes", 120)]:
            self.tree.heading(col, text=self.t(key), anchor="w")
            self.tree.column(col, width=width, stretch=(col == "note"), anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._use_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: (self._update_buttons(), self._render_model_detail()))
        self.tree.bind("<Button-3>", self._models_menu)

        self.model_detail = tk.StringVar()
        ttk.Label(card, textvariable=self.model_detail, style="Muted.TLabel", wraplength=720,
                  justify="left").pack(anchor="w", pady=(10, 0))
        buttons = ttk.Frame(card)
        buttons.pack(fill="x", pady=(10, 0))
        self.use_btn = ttk.Button(buttons, text=self.t("btn_use"), style="Accent.TButton",
                                  command=self._use_selected)
        self.use_btn.pack(side="left")
        ttk.Button(buttons, text=self.t("btn_import_folder"), command=self._import_folder).pack(side="left", padx=6)
        ttk.Button(buttons, text=self.t("btn_import_hf"), command=self._import_hf).pack(side="left")
        self.disk_var = tk.StringVar()
        ttk.Label(buttons, textvariable=self.disk_var, style="Muted.TLabel").pack(side="right")
        ttk.Label(page, text=self.t("models_tip"), style="Muted.TLabel").pack(anchor="w")

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
        if not hasattr(self, "tree"):
            return
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        active = self.engine.transcriber.source if self.engine.transcriber else None
        all_m = models.all_models(self.config.custom_models)
        labels = GROUP_LABELS.get(self.config.ui_language, GROUP_LABELS["en"])
        total = 0
        for group in models.GROUPS:
            members = [m for m in all_m if m.group == group]
            if not members:
                continue
            gid = f"group:{group}"
            self.tree.insert("", "end", iid=gid, text=labels[group], open=True, tags=("group",))
            for m in members:
                downloaded = models.is_downloaded(m.source)
                if downloaded and not models.is_local_folder(m.source):
                    total += models.disk_size(m.source)
                if m.source == self.engine.loading_source:
                    status = self.t("st_loading")
                elif m.source == active:
                    status = self.t("st_in_use")
                elif downloaded:
                    status = self.t("st_downloaded")
                else:
                    status = self.t("st_not_downloaded")
                self.tree.insert(gid, "end", iid=m.source, text=m.label,
                                 values=(m.size, m.speed, m.accuracy, status, self._note_for(m)))
        self.disk_var.set(self.t("disk_used", size=models.human_size(total)))
        keep = [s for s in selected if self.tree.exists(s)]
        if keep:
            self.tree.selection_set(keep)
        elif active and self.tree.exists(active):
            self.tree.selection_set(active)
        self._update_buttons()
        self._render_model_detail()

    def _render_model_detail(self) -> None:
        m = self._selected()
        self.model_detail.set(f"{m.label} — {self._note_for(m)}   ({m.source})" if m else "")

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

    def _use_selected(self, m: models.ModelInfo | None = None) -> None:
        m = m or self._selected()
        if m is None or self.engine.loading_source is not None:
            return
        if not models.is_downloaded(m.source):
            size = f" ({m.size})" if m.size else ""
            if not messagebox.askyesno(self.t("dl_title"), self.t("dl_msg", name=m.label, size=size),
                                       parent=self.root):
                return
        self.engine.load_model(m.source)

    def _download_only(self, m: models.ModelInfo) -> None:
        size = f" ({m.size})" if m.size else ""
        if not messagebox.askyesno(self.t("dl_title"), self.t("dl_only_msg", name=m.label, size=size),
                                   parent=self.root):
            return
        self._set_status("status_downloading", "busy", busy=True, name=m.label)

        def work():
            try:
                models.resolve(m.source)
                self.call_soon(lambda: (self._set_last(self.t("downloaded_msg", name=m.label)),
                                        self._refresh_models(), self._set_ready()))
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                self.call_soon(lambda: (self._set_ready(), messagebox.showerror(
                    self.t("model_error_title"), self.t("model_error_msg", name=m.label, err=err),
                    parent=self.root)))

        threading.Thread(target=work, daemon=True).start()

    def _delete_model_files(self, m: models.ModelInfo) -> None:
        size = models.human_size(models.disk_size(m.source))
        if not messagebox.askyesno(self.t("delete_files_title"), self.t("delete_files_msg", name=m.label, size=size),
                                   icon="warning", parent=self.root):
            return
        try:
            models.delete_files(m.source)
        except OSError as exc:
            messagebox.showerror(self.t("delete_files_title"), str(exc), parent=self.root)
        self._refresh_models()

    def _open_model_folder(self, m: models.ModelInfo) -> None:
        try:
            os.startfile(models.resolve(m.source, local_only=True))  # noqa: S606
        except Exception:  # noqa: BLE001
            pass

    def _models_menu(self, event) -> None:
        iid = self._tree_row_at(self.tree, event)
        m = self._selected() if iid else None
        if m is None:
            return
        active = self.engine.transcriber.source if self.engine.transcriber else None
        downloaded = models.is_downloaded(m.source)
        busy = self.engine.loading_source is not None
        menu = self._menu()
        menu.add_command(label=self.t("btn_use"), command=lambda: self._use_selected(m),
                         state="disabled" if m.source == active or busy else "normal")
        if not downloaded:
            menu.add_command(label=self.t("download_only"), command=lambda: self._download_only(m))
        menu.add_separator()
        if downloaded:
            menu.add_command(label=self.t("open_folder"), command=lambda: self._open_model_folder(m))
        url = models.hf_url(m.source)
        if url:
            menu.add_command(label=self.t("open_hf"), command=lambda: webbrowser.open(url))
        menu.add_command(label=self.t("copy_id"), command=lambda: (self.root.clipboard_clear(),
                                                                  self.root.clipboard_append(m.source)))
        if (downloaded and not models.is_local_folder(m.source)) or m.custom:
            menu.add_separator()
        if downloaded and not models.is_local_folder(m.source):
            menu.add_command(label=self.t("delete_files"), command=lambda: self._delete_model_files(m),
                             state="disabled" if m.source == active else "normal")
        if m.custom:
            menu.add_command(label=self.t("btn_remove"), command=lambda: self._remove_custom(m),
                             state="disabled" if m.source == active else "normal")
        self._popup(menu, event)

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

    def _remove_custom(self, m: models.ModelInfo) -> None:
        if not messagebox.askyesno(self.t("remove_title"), self.t("remove_msg", name=m.label), parent=self.root):
            return
        self.config.custom_models = [c for c in self.config.custom_models if c["source"] != m.source]
        self.config.save()
        self._refresh_models()

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
        self._mics = [None] + list_microphones()
        names = [self.t("mic_default")] + self._mics[1:]
        self.mic_combo = ttk.Combobox(row, state="readonly", width=48, values=names)
        cur = self.config.input_device if self.config.input_device in self._mics else None
        self.mic_combo.current(self._mics.index(cur))
        self.mic_combo.bind("<<ComboboxSelected>>", self._on_mic)
        self.mic_combo.pack(side="left")
        self.mic_test_btn = ttk.Button(row, text=self.t("mic_test"), command=self._toggle_mic_test)
        self.mic_test_btn.pack(side="left", padx=10)
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

        # Folders & about
        c = self._card(body, self.t("set_about"), **inner_pad)
        ttk.Label(c, text=self.t("about_text", version=__version__), style="Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=self.t("open_models_dir"), command=self._open_models_dir).pack(side="left")
        ttk.Button(row, text=self.t("open_settings_dir"),
                   command=lambda: os.startfile(SETTINGS_DIR)).pack(side="left", padx=6)  # noqa: S606
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

    # ================================================================== page: AI writing
    def _text_box(self, parent, height: int, text: str = "") -> tk.Text:
        pal = self.pal
        box = tk.Text(parent, height=height, wrap="word", font=self.fonts.body, bg=pal["key_bg"], fg=pal["text"],
                      insertbackground=pal["text"], relief="flat", padx=10, pady=8, highlightthickness=1,
                      highlightbackground=pal["key_border"], highlightcolor=pal["accent"], undo=True)
        box.insert("1.0", text)
        return box

    def _page_writing(self, page: ttk.Frame) -> None:
        self._page_header(page, "writing")
        scroll = ScrollFrame(page, self.pal["bg"])
        scroll.pack(fill="both", expand=True)
        body = scroll.inner
        pad = {"padx": (0, 14)}

        # --- model
        c = self._card(body, self.t("wr_model_title"), self.t("wr_model_sub"), **pad)
        row = ttk.Frame(c)
        row.pack(fill="x")
        ui = self.config.ui_language
        self._llms = list(writer.LLM_CATALOG)
        if self.config.writing_model not in [m.source for m in self._llms]:
            self._llms.append(writer.LlmInfo(self.config.writing_model, self.config.writing_model, "?", "", ""))
        self.llm_combo = ttk.Combobox(row, state="readonly", width=50, values=[
            f"{m.label}  ·  {m.size}  ·  {m.note_fr if ui == 'fr' else m.note_en}" for m in self._llms])
        self.llm_combo.current([m.source for m in self._llms].index(self.config.writing_model))
        self.llm_combo.bind("<<ComboboxSelected>>", self._on_llm_selected)
        self.llm_combo.pack(side="left")
        self.llm_btn = ttk.Button(row, text=self.t("wr_load"), style="Accent.TButton", command=self._llm_load)
        self.llm_btn.pack(side="left", padx=(10, 0))
        ttk.Button(row, text=self.t("wr_unload"), command=self.engine.unload_writer).pack(side="left", padx=(6, 0))
        self.llm_status = tk.StringVar()
        ttk.Label(c, textvariable=self.llm_status, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.preload_var = tk.BooleanVar(value=self.config.writer_preload)
        ttk.Checkbutton(c, text=self.t("wr_keep_loaded"), style="Switch.TCheckbutton", variable=self.preload_var,
                        command=self._on_preload).pack(anchor="w", pady=(8, 0))
        self._render_llm_status()

        # --- presets: list + editor
        c = self._card(body, self.t("wr_presets_title"), self.t("wr_presets_sub"), **pad)
        split = ttk.Frame(c)
        split.pack(fill="x")
        left = ttk.Frame(split)
        left.pack(side="left", fill="y")
        self.preset_tree = ttk.Treeview(left, columns=("name", "key"), show="headings", height=7,
                                        selectmode="browse")
        self.preset_tree.heading("name", text=self.t("wr_col_name"), anchor="w")
        self.preset_tree.heading("key", text=self.t("wr_col_key"), anchor="w")
        self.preset_tree.column("name", width=190, anchor="w")
        self.preset_tree.column("key", width=110, anchor="w")
        self.preset_tree.pack(fill="y", expand=True)
        self.preset_tree.bind("<<TreeviewSelect>>", self._on_preset_select)
        self.preset_tree.bind("<Button-3>", self._preset_menu)
        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text=self.t("wr_new"), command=self._preset_new).pack(side="left")
        ttk.Button(btns, text=self.t("wr_duplicate"), command=self._preset_duplicate).pack(side="left", padx=6)
        ttk.Button(btns, text=self.t("delete"), command=self._preset_delete).pack(side="left")

        ed = ttk.Frame(split)
        ed.pack(side="left", fill="both", expand=True, padx=(18, 0))
        ttk.Label(ed, text=self.t("wr_name")).pack(anchor="w")
        self.preset_name = ttk.Entry(ed)
        self.preset_name.pack(fill="x", pady=(2, 10))
        ttk.Label(ed, text=self.t("wr_hotkey")).pack(anchor="w")
        self.preset_key_row = ttk.Frame(ed)
        self.preset_key_row.pack(fill="x", pady=(4, 10))
        ttk.Label(ed, text=self.t("wr_instructions")).pack(anchor="w")
        ttk.Label(ed, text=self.t("wr_instructions_hint"), style="Muted.TLabel", wraplength=380,
                  justify="left").pack(anchor="w")
        self.preset_text = self._text_box(ed, 9)
        self.preset_text.pack(fill="both", expand=True, pady=(4, 8))
        bar = ttk.Frame(ed)
        bar.pack(fill="x")
        ttk.Button(bar, text=self.t("wr_save"), style="Accent.TButton", command=self._preset_save).pack(side="left")
        self.preset_saved = ttk.Label(bar, text="", style="Muted.TLabel")
        self.preset_saved.pack(side="left", padx=10)
        ttk.Button(bar, text=self.t("wr_reset"), command=self._presets_reset).pack(side="right")
        ttk.Label(c, text=self.t("wr_key_note"), style="Muted.TLabel", wraplength=760,
                  justify="left").pack(anchor="w", pady=(12, 0))
        self._editing_preset: str | None = None
        self._refresh_presets()

        # --- signature
        c = self._card(body, self.t("wr_signature_title"), self.t("wr_signature_sub"), **pad)
        self.signature_box = self._text_box(c, 4, self.config.signature)
        self.signature_box.pack(fill="x")
        self.signature_box.bind("<FocusOut>", lambda _e: self._save_signature())

        # --- test
        c = self._card(body, self.t("wr_test_title"), self.t("wr_test_sub"), **pad)
        self.test_in = self._text_box(c, 4, self.t("wr_test_sample"))
        self.test_in.pack(fill="x")
        row = ttk.Frame(c)
        row.pack(fill="x", pady=8)
        self.test_btn = ttk.Button(row, text=self.t("wr_test_btn"), style="Accent.TButton", command=self._preset_test)
        self.test_btn.pack(side="left")
        self.test_info = ttk.Label(row, text="", style="Muted.TLabel")
        self.test_info.pack(side="left", padx=10)
        self.test_out = self._text_box(c, 9)
        self.test_out.pack(fill="x")

    # ---- writing model
    def _llm_info(self) -> writer.LlmInfo:
        return next((m for m in self._llms if m.source == self.config.writing_model), self._llms[0])

    def _render_llm_status(self) -> None:
        if not hasattr(self, "llm_status"):
            return
        eng = self.engine
        info = self._llm_info()
        if eng.writer_loading:
            downloaded = writer.is_downloaded(info.source)
            text = self.t("wr_st_loading") if downloaded else self.t("wr_st_downloading", name=info.label,
                                                                      size=info.size)
        elif eng.writer is not None and eng.writer.source == info.source:
            text = self.t("wr_st_gpu" if eng.writer.device == "cuda" else "wr_st_cpu")
        elif writer.is_downloaded(info.source):
            text = self.t("wr_st_disk")
        else:
            text = self.t("wr_st_missing", size=info.size)
        self.llm_status.set(text)
        self.llm_btn.configure(state="disabled" if eng.writer_loading else "normal")

    def _on_llm_selected(self, _e=None) -> None:
        self.config.writing_model = self._llms[self.llm_combo.current()].source
        self.config.save()
        if self.engine.writer is not None and writer.is_downloaded(self.config.writing_model):
            self.engine.load_writer()
        self._render_llm_status()

    def _llm_load(self) -> None:
        info = self._llm_info()
        if not writer.is_downloaded(info.source) and not messagebox.askyesno(
                self.t("wr_dl_title"), self.t("wr_dl_confirm", name=info.label, size=info.size), parent=self.root):
            return
        self.engine.load_writer(force=True)
        self._render_llm_status()

    def _on_preload(self) -> None:
        self.config.writer_preload = self.preload_var.get()
        self.config.save()
        if not self.config.writer_preload:
            self.engine.unload_writer()

    def _save_signature(self) -> None:
        if hasattr(self, "signature_box"):
            self.config.signature = self.signature_box.get("1.0", "end").strip()
            self.config.save()

    # ---- presets
    def _refresh_presets(self, select: str | None = None) -> None:
        tree = self.preset_tree
        keep = select or self._editing_preset
        tree.delete(*tree.get_children())
        for p in self.config.presets or []:
            tree.insert("", "end", iid=p["id"], values=(p["name"], self._hotkey_label(p["hotkey"])
                                                        if p.get("hotkey") else "—"))
        ids = [p["id"] for p in self.config.presets or []]
        target = keep if keep in ids else (ids[0] if ids else None)
        if target:
            tree.selection_set(target)
            tree.focus(target)
        else:
            self._editing_preset = None
        self._load_preset_editor()

    def _on_preset_select(self, _e=None) -> None:
        sel = self.preset_tree.selection()
        if sel and sel[0] == self._editing_preset:
            return
        self._store_editor()  # keep unsaved edits of the preset we're leaving (saved with the next Save)
        self._load_preset_editor()

    def _load_preset_editor(self) -> None:
        sel = self.preset_tree.selection()
        p = self.engine.preset(sel[0]) if sel else None
        self._editing_preset = p["id"] if p else None
        self.preset_name.delete(0, "end")
        self.preset_text.delete("1.0", "end")
        for w in self.preset_key_row.winfo_children():
            w.destroy()
        self.preset_saved.configure(text="")
        if not p:
            return
        self.preset_name.insert(0, p["name"])
        self.preset_text.insert("1.0", p.get("instructions", ""))
        self.preset_text.edit_reset()
        self._keycaps(self.preset_key_row, p.get("hotkey", "")).pack(side="left")
        ttk.Button(self.preset_key_row, text=self.t("change"),
                   command=lambda: self._record_hotkey(f"preset:{p['id']}")).pack(side="left", padx=(12, 0))
        if p.get("hotkey"):
            ttk.Button(self.preset_key_row, text=self.t("wr_remove_key"),
                       command=lambda: self._set_preset_hotkey(p["id"], "")).pack(side="left", padx=6)

    def _store_editor(self) -> None:
        """Copy the editor's name/instructions into the preset being edited (no save)."""
        p = self.engine.preset(self._editing_preset)
        if p:
            p["name"] = self.preset_name.get().strip() or p["name"]
            p["instructions"] = self.preset_text.get("1.0", "end").strip()

    def _preset_save(self) -> None:
        self._store_editor()
        self._save_signature()
        self.engine.apply_presets()
        self._refresh_presets()
        self._render_home_presets()
        self.preset_saved.configure(text=self.t("wr_saved"))

    def _set_preset_hotkey(self, pid: str, combo: str) -> None:
        p = self.engine.preset(pid)
        if not p:
            return
        self._store_editor()
        p["hotkey"] = "+".join(normalize_hotkey(combo))
        self.engine.apply_presets()
        self._build()

    def _preset_new(self) -> None:
        self._store_editor()
        p = {"id": writer.new_preset_id(), "name": self.t("wr_new_name"), "hotkey": "", "instructions": ""}
        self.config.presets.append(p)
        self.engine.apply_presets()
        self._refresh_presets(select=p["id"])
        self.preset_name.focus_set()
        self.preset_name.select_range(0, "end")

    def _preset_duplicate(self) -> None:
        self._store_editor()
        src = self.engine.preset(self._editing_preset)
        if not src:
            return
        p = {**src, "id": writer.new_preset_id(), "name": f"{src['name']} {self.t('wr_copy_suffix')}", "hotkey": ""}
        self.config.presets.append(p)
        self.engine.apply_presets()
        self._refresh_presets(select=p["id"])

    def _preset_delete(self) -> None:
        p = self.engine.preset(self._editing_preset)
        if p and messagebox.askyesno(self.t("delete"), self.t("wr_delete_confirm", name=p["name"]), parent=self.root):
            self.config.presets.remove(p)
            self._editing_preset = None
            self.engine.apply_presets()
            self._refresh_presets()
            self._render_home_presets()

    def _presets_reset(self) -> None:
        if messagebox.askyesno(self.t("wr_reset"), self.t("wr_reset_confirm"), parent=self.root):
            self.config.presets = None
            self.config.ensure_presets()
            self._editing_preset = None
            self.engine.apply_presets()
            self._build()

    def _preset_menu(self, event) -> None:
        if not self._tree_row_at(self.preset_tree, event):
            return
        pid = self.preset_tree.selection()[0]
        m = self._menu()
        m.add_command(label=self.t("wr_hotkey") + "…", command=lambda: self._record_hotkey(f"preset:{pid}"))
        if (self.engine.preset(pid) or {}).get("hotkey"):
            m.add_command(label=self.t("wr_remove_key"), command=lambda: self._set_preset_hotkey(pid, ""))
        m.add_command(label=self.t("wr_duplicate"), command=self._preset_duplicate)
        m.add_separator()
        m.add_command(label=self.t("delete"), command=self._preset_delete)
        self._popup(m, event)

    def _preset_test(self) -> None:
        self._store_editor()
        self._save_signature()
        p = self.engine.preset(self._editing_preset)
        text = self.test_in.get("1.0", "end").strip()
        if not p or not text:
            return
        if not writer.is_downloaded(self.config.writing_model):
            info = self._llm_info()
            if not messagebox.askyesno(self.t("wr_dl_title"), self.t("wr_dl_confirm", name=info.label, size=info.size),
                                       parent=self.root):
                return
        self.test_btn.configure(state="disabled")
        self.test_info.configure(text=self.t("wr_test_running"))
        preset = dict(p)

        def work():
            import time

            started = time.perf_counter()
            try:
                out, info = self.engine.rewrite(text, preset), f"{time.perf_counter() - started:.1f} s"
            except Exception as exc:  # noqa: BLE001
                out, info = "", str(exc)[:200]
            self.call_soon(lambda: self._show_test_result(out, info))

        threading.Thread(target=work, daemon=True).start()

    def _show_test_result(self, out: str, info: str) -> None:
        if not hasattr(self, "test_out") or not self.test_out.winfo_exists():
            return
        self.test_btn.configure(state="normal")
        self.test_info.configure(text=info)
        self.test_out.delete("1.0", "end")
        self.test_out.insert("1.0", out)
        self._render_llm_status()

    def _render_home_presets(self) -> None:
        if not hasattr(self, "home_presets_var"):
            return
        parts = [f"{self._hotkey_label(p['hotkey'])} {p['name']}" for p in self.config.presets or [] if p.get("hotkey")]
        self.home_presets_var.set(f"{self.t('home_presets')}  " + "   ·   ".join(parts) if parts else "")

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
        choices = {"main": PRESETS, "lang": LANG_PRESETS, "paste": PASTE_PRESETS}.get(target, WRITING_PRESET_KEYS)
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
        elif target.startswith("preset:"):
            self._set_preset_hotkey(target.split(":", 1)[1], combo)
            return
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

    # ================================================================== tray
    def _tray_menu(self, pystray):
        def lang_item(code):
            return pystray.MenuItem(
                self.lang_name(code),
                lambda: self.call_soon(lambda: self.engine.set_language(code)),
                checked=lambda _item: self.config.language == code, radio=True)

        lang_items = [lang_item(None)] + [lang_item(c) for c in self.config.favorite_languages]
        return pystray.Menu(
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
        elif kind == "transcribing":
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
        elif kind == "pasted_last":
            if self.config.overlay:
                self.overlay.flash(self.t("overlay_pasted"))
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

    def run(self, start_hidden: bool = False) -> None:
        if start_hidden and self.tray.available:
            self.root.withdraw()
        self.engine.start()
        self.root.after(60, self._poll)
        self.root.mainloop()
