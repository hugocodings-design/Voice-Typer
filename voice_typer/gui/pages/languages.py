"""Page Langues: favorites, language shortcut."""

import tkinter as tk
from tkinter import ttk

from voice_typer import languages, ui_theme


class LanguagesPage:
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
