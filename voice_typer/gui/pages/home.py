"""Page Accueil: status hero, language buttons, shortcuts, history."""

import datetime as dt
import tkinter as tk
from tkinter import ttk

from voice_typer.gui import dialogs as messagebox

from voice_typer import clipboard, languages
from voice_typer.config import save_history


class HomePage:
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
        st = self.engine.remote_status
        if self.engine.remote is not None:
            parts.append(self.t("chip_remote_ok") if st and st[0] else self.t("chip_remote_down"))
        elif self.engine.host is not None:
            parts.append(self.t("chip_host"))
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
            clipboard.set_text(item.get("text", ""))

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
                          command=lambda: clipboard.set_text(raw))
        m.add_command(label=self.t("hist_to_dict"), command=self._history_add_to_dict)
        m.add_separator()
        m.add_command(label=self.t("delete"), command=self._history_delete)
        m.add_command(label=self.t("history_clear"), command=self._history_clear)
        self._popup(m, event)
