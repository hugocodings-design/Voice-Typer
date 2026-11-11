"""Page Écriture IA: writing model, presets, signature, test."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from voice_typer import ui_theme, winapp, writer
from voice_typer.gui.common import ScrollFrame
from voice_typer.hotkey import normalize as normalize_hotkey


class WritingPage:
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

        # --- rewrite the selected text
        c = self._card(body, self.t("rw_title"), self.t("rw_sub"), **pad)
        row = ttk.Frame(c)
        row.pack(fill="x")
        self._keycaps(row, self.config.rewrite_hotkey).pack(side="left")
        ttk.Button(row, text=self.t("change"), command=lambda: self._record_hotkey("rewrite")).pack(
            side="left", padx=(12, 0))
        if self.config.rewrite_hotkey:
            ttk.Button(row, text=self.t("wr_remove_key"),
                       command=lambda: (self.engine.set_rewrite_hotkey(""), self._build())).pack(side="left", padx=6)
        ttk.Label(row, text=self.t("rw_with")).pack(side="left", padx=(24, 8))
        names = [p["name"] for p in self.config.presets or []]
        ids = [p["id"] for p in self.config.presets or []]
        self.rw_combo = ttk.Combobox(row, state="readonly", width=24, values=names)
        if self.config.rewrite_preset in ids:
            self.rw_combo.current(ids.index(self.config.rewrite_preset))
        elif ids:
            self.rw_combo.current(0)
        self.rw_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_rewrite_preset(ids))
        self.rw_combo.pack(side="left")

        # --- automatic preset per application
        c = self._card(body, self.t("ap_title"), self.t("ap_sub"), **pad)
        self.ap_tree = ttk.Treeview(c, columns=("app", "preset"), show="headings", height=4, selectmode="browse")
        self.ap_tree.heading("app", text=self.t("ap_col_app"), anchor="w")
        self.ap_tree.heading("preset", text=self.t("ap_col_preset"), anchor="w")
        self.ap_tree.column("app", width=300, anchor="w")
        self.ap_tree.column("preset", width=260, anchor="w")
        self.ap_tree.pack(fill="x")
        self.ap_tree.bind("<Button-3>", self._ap_menu)
        self.ap_tree.bind("<Delete>", lambda _e: self._ap_delete())
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text=self.t("ap_add"), style="Accent.TButton", command=self._ap_add).pack(side="left")
        ttk.Button(row, text=self.t("delete"), command=self._ap_delete).pack(side="left", padx=6)
        self._refresh_app_presets()

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

    # ---- rewrite selection / per-app presets
    def _on_rewrite_preset(self, ids: list[str]) -> None:
        i = self.rw_combo.current()
        if 0 <= i < len(ids):
            self.config.rewrite_preset = ids[i]
            self.config.save()

    def _refresh_app_presets(self) -> None:
        tree = self.ap_tree
        tree.delete(*tree.get_children())
        for i, rule in enumerate(self.config.app_presets):
            p = self.engine.preset(rule.get("preset"))
            tree.insert("", "end", iid=str(i), values=(
                f"{winapp.friendly(rule['app'])}  ({rule['app']})", p["name"] if p else "—"))

    def _ap_delete(self) -> None:
        sel = self.ap_tree.selection()
        if sel:
            del self.config.app_presets[int(sel[0])]
            self.config.save()
            self._refresh_app_presets()

    def _ap_menu(self, event) -> None:
        if not self._tree_row_at(self.ap_tree, event):
            return
        m = self._menu()
        m.add_command(label=self.t("delete"), command=self._ap_delete)
        self._popup(m, event)

    def _ap_add(self) -> None:
        """Small dialog: pick an application (common work apps or any .exe) and a preset."""
        presets = self.config.presets or []
        if not presets:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(self.t("ap_add"))
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.configure(bg=self.pal["bg"])
        box = ttk.Frame(dlg, padding=22)
        box.pack()
        ttk.Label(box, text=self.t("ap_dlg_app")).grid(row=0, column=0, sticky="w", pady=6)
        apps = sorted({f"{name}  ({exe})" for exe, name in winapp.KNOWN_APPS.items()})
        app_box = ttk.Combobox(box, width=34, values=apps)
        app_box.grid(row=0, column=1, padx=(12, 0), pady=6)
        ttk.Label(box, text=self.t("ap_dlg_hint"), style="Muted.TLabel", wraplength=360,
                  justify="left").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(box, text=self.t("ap_col_preset")).grid(row=2, column=0, sticky="w", pady=(12, 6))
        preset_box = ttk.Combobox(box, state="readonly", width=34, values=[p["name"] for p in presets])
        preset_box.current(0)
        preset_box.grid(row=2, column=1, padx=(12, 0), pady=(12, 6))

        def ok():
            raw = app_box.get().strip()
            exe = raw[raw.rfind("(") + 1:raw.rfind(")")] if raw.endswith(")") else raw
            exe = exe.strip().lower()
            if exe and not exe.endswith(".exe"):
                exe += ".exe"
            if not exe:
                return
            self.config.app_presets = [r for r in self.config.app_presets if r.get("app") != exe]
            self.config.app_presets.append({"app": exe, "preset": presets[preset_box.current()]["id"]})
            self.config.save()
            dlg.destroy()
            self._refresh_app_presets()

        row = ttk.Frame(box)
        row.grid(row=3, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(row, text=self.t("cancel"), command=dlg.destroy).pack(side="right")
        ttk.Button(row, text=self.t("add"), style="Accent.TButton", command=ok).pack(side="right", padx=6)
        dlg.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dlg.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_reqheight()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        ui_theme._dark_title_bar(dlg, self.mode == "dark")  # noqa: SLF001
        dlg.grab_set()
        app_box.focus_set()

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
