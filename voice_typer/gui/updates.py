"""Update notice (banner above every page), the Updates card in Réglages and the install flow."""

import threading
import tkinter as tk
from tkinter import ttk

from voice_typer import __version__, portable, updater
from voice_typer.gui import dialogs as messagebox

FIRST_CHECK_MS = 20_000
EVERY_MS = 6 * 3600 * 1000


class UpdatesMixin:
    _update: dict | None = None
    _upd_busy = False
    _upd_hidden = False      # "Plus tard": hidden until the app restarts

    # ---- checking
    def _upd_schedule(self) -> None:
        self.root.after(FIRST_CHECK_MS, self._upd_auto)

    def _upd_auto(self) -> None:
        # Checking always runs: with automatic updates turned off, only a REQUIRED update is acted on.
        self._upd_check(manual=False)
        self.root.after(EVERY_MS, self._upd_auto)

    def _upd_check(self, manual: bool = True) -> None:
        if self._upd_busy:
            return
        if manual:
            self._upd_set_status(self.t("upd_checking"))

        def work():
            try:
                info, err = updater.check(), None
            except updater.UpdateError as exc:
                info, err = None, str(exc)
            self.call_soon(lambda: self._upd_result(info, err, manual))

        threading.Thread(target=work, daemon=True).start()

    def _upd_result(self, info: dict | None, err: str | None, manual: bool) -> None:
        if err:
            if manual:
                self._upd_set_status(self.t("upd_error", err=err[:160]))
            return
        if info is None:
            self._upd_set_status(self.t("upd_uptodate", version=__version__))
            return
        required = updater.is_required(info)
        if not manual and not required and (not self.config.auto_update
                                            or info["version"] == self.config.skipped_update):
            return
        is_new = self._update is None or self._update["version"] != info["version"]
        self._update = info
        if manual:
            self._upd_hidden = False
        self._upd_set_status(self.t("upd_available", version=info["version"]))
        self._upd_render_banner()
        self.tray.refresh()
        if is_new and not manual:
            self.tray.notify(self.t("upd_required_tray" if required else "upd_tray", version=info["version"]))
        if required:
            self._upd_install_when_idle()

    def _upd_install_when_idle(self) -> None:
        """Required update: install as soon as nothing is being dictated (checked every 30 s)."""
        if self._upd_busy or not updater.can_self_update() or not updater.is_required(self._update):
            return
        if self.engine.recorder.is_recording or getattr(self.engine, "busy", False):
            self.root.after(30_000, self._upd_install_when_idle)
            return
        self._upd_install()

    # ---- banner (above every page)
    def _upd_build_banner(self) -> None:
        pal = self.pal
        self.upd_banner = tk.Frame(self.content, bg=pal["accent_soft"], padx=16, pady=12,
                                   highlightthickness=1, highlightbackground=pal["accent"])
        top = tk.Frame(self.upd_banner, bg=pal["accent_soft"])
        top.pack(fill="x")
        self.upd_title = tk.Label(top, font=self.fonts.bold, bg=pal["accent_soft"], fg=pal["text"], anchor="w")
        self.upd_title.pack(side="left")
        self.upd_btns = tk.Frame(top, bg=pal["accent_soft"])
        self.upd_btns.pack(side="right")
        ttk.Button(self.upd_btns, text=self.t("upd_install"), style="Accent.TButton",
                   command=self._upd_install).pack(side="right")
        self.upd_later_btn = ttk.Button(self.upd_btns, text=self.t("upd_later"), command=self._upd_later)
        self.upd_skip_btn = ttk.Button(self.upd_btns, text=self.t("upd_skip"), command=self._upd_skip)
        self.upd_later_btn.pack(side="right", padx=6)
        self.upd_skip_btn.pack(side="right")
        self.upd_text = tk.Label(self.upd_banner, font=self.fonts.small, bg=pal["accent_soft"], fg=pal["muted"],
                                 anchor="w", justify="left", wraplength=720)
        self.upd_text.pack(fill="x", pady=(4, 0))
        self.upd_progress = ttk.Progressbar(self.upd_banner, mode="determinate", maximum=100)
        self._upd_render_banner()

    def _upd_render_banner(self) -> None:
        if not hasattr(self, "upd_banner"):
            return
        info = self._update
        if info is None or self._upd_hidden:
            self.upd_banner.pack_forget()
            return
        required = updater.is_required(info)
        self.upd_title.configure(text=self.t("upd_required_banner" if required else "upd_banner",
                                             version=info["version"]))
        if required:  # only "Install now"
            self.upd_later_btn.pack_forget()
            self.upd_skip_btn.pack_forget()
        elif not self.upd_later_btn.winfo_manager():  # not packed (hidden by a required update)
            self.upd_later_btn.pack(side="right", padx=6)
            self.upd_skip_btn.pack(side="right")
        notes = info.get(f"notes_{self.config.ui_language}") or info.get("notes_en") or ""
        size = info.get("size") or 0
        extra = self.t("upd_size", mb=round(size / 1e6)) if size else ""
        if not updater.can_self_update():
            extra = self.t("upd_dev")
        self.upd_text.configure(text="  ".join(x for x in (notes, extra) if x))
        current = self.pages.get(self._page)
        self.upd_banner.pack(fill="x", pady=(0, 14), before=current)

    def _upd_later(self) -> None:
        self._upd_hidden = True
        self._upd_render_banner()

    def _upd_skip(self) -> None:
        if self._update:
            self.config.skipped_update = self._update["version"]
            self.config.save()
        self._upd_later()

    # ---- install
    def _upd_install(self) -> None:
        info = self._update
        if info is None or self._upd_busy:
            return
        if not updater.can_self_update():
            messagebox.showinfo(self.t("upd_card"), self.t("upd_dev"), parent=self.root)
            return
        if self.engine.recorder.is_recording:
            return
        self._upd_busy = True
        self._upd_hidden = False
        self._show_window()
        self._upd_render_banner()
        self.upd_btns.pack_forget()
        self.upd_progress.pack(fill="x", pady=(8, 0))
        self.upd_text.configure(text=self.t("upd_downloading", pct=0))

        def progress(done, total):
            pct = int(done * 100 / total) if total else 0
            self.call_soon(lambda: (self.upd_progress.configure(value=pct),
                                    self.upd_text.configure(text=self.t("upd_downloading", pct=pct))))

        def work():
            try:
                path = updater.download(info, progress)
            except updater.UpdateError as exc:
                err = str(exc)
                self.call_soon(lambda: self._upd_failed(err))
                return
            self.call_soon(lambda: self._upd_run(path))

        threading.Thread(target=work, daemon=True).start()

    def _upd_failed(self, err: str) -> None:
        self._upd_busy = False
        self.upd_progress.pack_forget()
        self.upd_btns.pack(side="right")
        self._upd_render_banner()
        messagebox.showerror(self.t("upd_card"), self.t("upd_failed", err=err[:300]), parent=self.root)

    def _upd_run(self, path) -> None:
        self.upd_text.configure(text=self.t("upd_installing"))
        self.root.update_idletasks()
        try:
            if portable.is_portable():
                updater.install_portable(path, self._update["version"])
            else:
                updater.install(path)
        except (OSError, updater.UpdateError) as exc:
            self._upd_failed(str(exc))
            return
        self.root.after(400, self._quit)

    # ---- Réglages card
    def _upd_card(self, body, pad) -> None:
        c = self._card(body, self.t("upd_card"), **pad)
        ttk.Label(c, text=self.t("upd_current", version=__version__)).pack(anchor="w")
        self.auto_update_var = tk.BooleanVar(value=self.config.auto_update)
        ttk.Checkbutton(c, text=self.t("upd_auto"), style="Switch.TCheckbutton", variable=self.auto_update_var,
                        command=self._upd_on_auto).pack(anchor="w", pady=(10, 0))
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=self.t("upd_check"), command=lambda: self._upd_check(manual=True)).pack(side="left")
        self.upd_status_var = getattr(self, "upd_status_var", None) or tk.StringVar()
        ttk.Label(row, textvariable=self.upd_status_var, style="Muted.TLabel").pack(side="left", padx=12)
        ttk.Label(c, text=self.t("upd_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(10, 0))

    def _upd_on_auto(self) -> None:
        self.config.auto_update = self.auto_update_var.get()
        self.config.save()

    def _upd_set_status(self, text: str) -> None:
        if not hasattr(self, "upd_status_var"):
            self.upd_status_var = tk.StringVar()
        self.upd_status_var.set(text)
