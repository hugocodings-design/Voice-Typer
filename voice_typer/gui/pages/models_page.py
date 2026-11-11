"""Page Modèles IA: catalog, download, import."""

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from voice_typer.gui import dialogs as messagebox
from voice_typer.gui import dialogs as simpledialog

from voice_typer import models
from voice_typer.i18n import GROUP_LABELS, MODEL_NOTES


class ModelsPage:
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
        if downloaded:
            menu.add_separator()
            menu.add_command(label=self.t("open_folder"), command=lambda: self._open_model_folder(m))
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
