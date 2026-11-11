"""Page Dictionnaire: vocabulary + replacements."""

from tkinter import simpledialog, ttk


class DictionaryPage:
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
