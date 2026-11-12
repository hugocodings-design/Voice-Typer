"""Page Dictionnaire: vocabulary + replacements, general or for one application."""

import tkinter as tk
from tkinter import ttk

from voice_typer import winapp
from voice_typer.gui import dialogs as simpledialog


class DictionaryPage:
    # ================================================================== page: dictionary
    def _page_dictionary(self, page: ttk.Frame) -> None:
        self._page_header(page, "dictionary")
        scope = ttk.Frame(page)
        scope.pack(fill="x", pady=(0, 10))
        ttk.Label(scope, text=self.t("dict_scope")).pack(side="left")
        self.dict_scope_combo = ttk.Combobox(scope, state="readonly", width=40)
        self.dict_scope_combo.pack(side="left", padx=8)
        self.dict_scope_combo.bind("<<ComboboxSelected>>", lambda _e: self._dict_on_scope())
        ttk.Button(scope, text=self.t("dict_add_app"), command=self._dict_add_app).pack(side="left")
        self.dict_remove_btn = ttk.Button(scope, text=self.t("dict_remove_app"), command=self._dict_remove_app)
        self.dict_remove_btn.pack(side="left", padx=6)
        self.dict_scope_note = ttk.Label(page, style="Muted.TLabel", wraplength=740, justify="left")
        self.dict_scope_note.pack(anchor="w", pady=(0, 8))
        if not hasattr(self, "_dict_app"):
            self._dict_app = None      # None = general dictionary, else "outlook.exe"
        self._dict_fill_scopes()
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

    # ---- which dictionary is being edited: general, or one application's
    def _dict_entry(self) -> dict | None:
        return next((d for d in self.config.app_dictionaries if d.get("app") == self._dict_app), None)

    def _vocab_list(self) -> list:
        e = self._dict_entry()
        return e.setdefault("vocabulary", []) if e else self.config.vocabulary

    def _repl_list(self) -> list:
        e = self._dict_entry()
        return e.setdefault("replacements", []) if e else self.config.replacements

    def _dict_fill_scopes(self) -> None:
        apps = [d["app"] for d in self.config.app_dictionaries if d.get("app")]
        if self._dict_app not in apps:
            self._dict_app = None
        self._dict_scope_apps = [None] + apps
        self.dict_scope_combo.configure(values=[self.t("dict_scope_all")] + [
            self.t("dict_scope_app", app=f"{winapp.friendly(a)} ({a})") for a in apps])
        self.dict_scope_combo.current(self._dict_scope_apps.index(self._dict_app))
        self.dict_remove_btn.configure(state="normal" if self._dict_app else "disabled")
        self.dict_scope_note.configure(text=self.t("dict_scope_note_app" if self._dict_app else "dict_scope_note_all"))

    def _dict_on_scope(self) -> None:
        self._dict_app = self._dict_scope_apps[max(self.dict_scope_combo.current(), 0)]
        self._dict_fill_scopes()
        self._refresh_dictionary()

    def _dict_remove_app(self) -> None:
        if not self._dict_app:
            return
        if not simpledialog.askyesno(self.t("dict_remove_app"), self.t("dict_remove_confirm",
                                     app=winapp.friendly(self._dict_app)), parent=self.root, icon="warning"):
            return
        self.config.app_dictionaries = [d for d in self.config.app_dictionaries if d.get("app") != self._dict_app]
        self.config.save()
        self._dict_app = None
        self._dict_fill_scopes()
        self._refresh_dictionary()

    def _dict_add_app(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("dict_add_app"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.configure(bg=self.pal["bg"])
        box = ttk.Frame(dlg, padding=22)
        box.pack()
        ttk.Label(box, text=self.t("ap_dlg_app")).grid(row=0, column=0, sticky="w", pady=6)
        app_box = ttk.Combobox(box, width=34, values=winapp.app_choices())
        app_box.grid(row=0, column=1, padx=(12, 0), pady=6)
        app_box.focus_set()
        ttk.Label(box, text=self.t("ap_dlg_hint"), style="Muted.TLabel", wraplength=360,
                  justify="left").grid(row=1, column=0, columnspan=2, sticky="w")

        def ok(_e=None):
            exe = winapp.parse_app(app_box.get())
            if not exe:
                return
            if not any(d.get("app") == exe for d in self.config.app_dictionaries):
                self.config.app_dictionaries.append({"app": exe, "vocabulary": [], "replacements": []})
                self.config.save()
            self._dict_app = exe
            dlg.destroy()
            self._dict_fill_scopes()
            self._refresh_dictionary()

        app_box.bind("<Return>", ok)
        row = ttk.Frame(box)
        row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(row, text=self.t("cancel"), command=dlg.destroy).pack(side="right")
        ttk.Button(row, text=self.t("add"), style="Accent.TButton", command=ok).pack(side="right", padx=6)
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_reqheight()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dlg.grab_set()

    def _refresh_dictionary(self) -> None:
        self.vocab_tree.delete(*self.vocab_tree.get_children())
        for i, term in enumerate(self._vocab_list()):
            self.vocab_tree.insert("", "end", iid=str(i), values=(term,))
        self.repl_tree.delete(*self.repl_tree.get_children())
        for i, rule in enumerate(self._repl_list()):
            self.repl_tree.insert("", "end", iid=str(i), values=(rule.get("from", ""), rule.get("to", "")))
        self._render_chips()

    def _vocab_add(self) -> None:
        term = self.vocab_entry.get().strip()
        if term and term.lower() not in (t.lower() for t in self._vocab_list()):
            self._vocab_list().append(term)
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
        new = simpledialog.askstring(self.t("edit"), self.t("col_term"), initialvalue=self._vocab_list()[i],
                                     parent=self.root)
        if new and new.strip():
            self._vocab_list()[i] = new.strip()
            self.config.save()
            self._refresh_dictionary()

    def _vocab_delete(self) -> None:
        i = self._vocab_index()
        if i is not None:
            del self._vocab_list()[i]
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
        rules = self._repl_list()
        rules[:] = [r for r in rules if r.get("from", "").lower() != src.lower()]
        rules.append({"from": src, "to": dst})
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
        rule = self._repl_list().pop(i)
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
            del self._repl_list()[i]
            self.config.save()
            self._refresh_dictionary()

    def _repl_menu(self, event) -> None:
        if not self._tree_row_at(self.repl_tree, event):
            return
        m = self._menu()
        m.add_command(label=self.t("edit"), command=self._repl_edit)
        m.add_command(label=self.t("delete"), command=self._repl_delete)
        self._popup(m, event)
