"""Page Partage de puissance: share this PC's AI with other devices, or use another PC's."""

import time
import tkinter as tk
from tkinter import ttk

from voice_typer import remote
from voice_typer.gui import dialogs as messagebox
from voice_typer.gui.common import ScrollFrame

MODES = ["off", "host", "client"]


class RemotePage:
    def _page_remote(self, page: ttk.Frame) -> None:
        self._page_header(page, "remote")
        scroll = ScrollFrame(page, self.pal["bg"])
        scroll.pack(fill="both", expand=True)
        body = scroll.inner
        pad = {"padx": (0, 14)}

        # --- mode
        c = self._card(body, self.t("rm_mode_title"), self.t("rm_mode_sub"), **pad)
        self.rm_mode_var = tk.StringVar(value=self.config.remote_mode)
        for m in MODES:
            ttk.Radiobutton(c, text=self.t(f"rm_mode_{m}"), value=m, variable=self.rm_mode_var,
                            command=self._rm_on_mode).pack(anchor="w", pady=3)

        self.rm_cards = ttk.Frame(body)
        self.rm_cards.pack(fill="x")

        # --- host: this PC shares its power
        self.rm_host = ttk.Frame(self.rm_cards)
        c = self._card(self.rm_host, self.t("rm_host_title"), **pad)
        self.rm_host_status = tk.StringVar()
        ttk.Label(c, textvariable=self.rm_host_status, wraplength=700, justify="left").pack(anchor="w")
        stats = tk.Frame(c, bg=self.pal["card"])
        stats.pack(fill="x", pady=(14, 4))
        self.rm_stat_vars = {}
        for i, key in enumerate(("rm_stat_now", "rm_stat_total", "rm_stat_busy")):
            box = tk.Frame(stats, bg=self.pal["accent_soft"], padx=16, pady=10)
            box.grid(row=0, column=i, sticky="nsew", padx=(0, 10))
            stats.columnconfigure(i, weight=1, uniform="stat")
            var = tk.StringVar(value="0")
            self.rm_stat_vars[key] = var
            tk.Label(box, textvariable=var, font=self.fonts.h1, bg=self.pal["accent_soft"],
                     fg=self.pal["accent"]).pack(anchor="w")
            tk.Label(box, text=self.t(key), font=self.fonts.small, bg=self.pal["accent_soft"],
                     fg=self.pal["text"]).pack(anchor="w")

        c = self._card(self.rm_host, self.t("rm_code_title"), self.t("rm_code_sub"), **pad)
        row = ttk.Frame(c)
        row.pack(fill="x")
        ttk.Label(row, text=self.t("rm_address")).pack(side="left")
        self.rm_addr_combo = ttk.Combobox(row, state="readonly", width=46)
        self.rm_addr_combo.pack(side="left", padx=8)
        self.rm_addr_combo.bind("<<ComboboxSelected>>", lambda _e: self._rm_render_code())
        ttk.Button(row, text=self.t("rm_refresh"), command=self._rm_fill_addresses).pack(side="left")
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(10, 0))
        self.rm_code_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.rm_code_var, state="readonly", width=60).pack(
            side="left", fill="x", expand=True)
        ttk.Button(row, text=self.t("rm_copy_code"), style="Accent.TButton",
                   command=self._rm_copy_code).pack(side="left", padx=(8, 0))
        self.rm_addr_note = ttk.Label(c, style="Muted.TLabel", wraplength=700, justify="left")
        self.rm_addr_note.pack(anchor="w", pady=(10, 0))
        ttk.Button(c, text=self.t("rm_new_key"), command=self._rm_new_key).pack(anchor="w", pady=(10, 0))

        c = self._card(self.rm_host, self.t("rm_devices_title"), self.t("rm_devices_sub"), **pad)
        cols = ("name", "ip", "seen", "dict", "rew", "min")
        self.rm_tree = ttk.Treeview(c, columns=cols, show="headings", height=6, selectmode="browse")
        widths = {"name": 190, "ip": 130, "seen": 150, "dict": 80, "rew": 80, "min": 90}
        for col in cols:
            self.rm_tree.heading(col, text=self.t(f"rm_col_{col}"), anchor="w")
            self.rm_tree.column(col, width=widths[col], anchor="w")
        self.rm_tree.pack(fill="x")
        menu = self._menu()
        menu.add_command(label=self.t("rm_forget"), command=self._rm_forget)
        self.rm_tree.bind("<Button-3>", lambda e: self._tree_row_at(self.rm_tree, e) and self._popup(menu, e))
        ttk.Button(c, text=self.t("rm_forget_all"), command=lambda: self._rm_forget(all_=True)).pack(
            anchor="w", pady=(10, 0))

        # --- client: this PC uses another one
        self.rm_client = ttk.Frame(self.rm_cards)
        c = self._card(self.rm_client, self.t("rm_client_title"), self.t("rm_client_sub"), **pad)
        row = ttk.Frame(c)
        row.pack(fill="x")
        self.rm_paste_var = tk.StringVar()
        field = ttk.Entry(row, textvariable=self.rm_paste_var, width=60)
        field.pack(side="left", fill="x", expand=True)
        field.bind("<Return>", lambda _e: self._rm_connect())
        ttk.Button(row, text=self.t("rm_connect"), style="Accent.TButton", command=self._rm_connect).pack(
            side="left", padx=(8, 0))
        self.rm_client_status = tk.StringVar()
        self.rm_client_label = ttk.Label(c, textvariable=self.rm_client_status, wraplength=700, justify="left")
        self.rm_client_label.pack(anchor="w", pady=(12, 0))
        row = ttk.Frame(c)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=self.t("rm_test"), command=self._rm_test).pack(side="left")
        ttk.Button(row, text=self.t("rm_disconnect"), command=self._rm_disconnect).pack(side="left", padx=8)
        ttk.Label(c, text=self.t("rm_fallback_note"), style="Muted.TLabel", wraplength=700,
                  justify="left").pack(anchor="w", pady=(12, 0))

        # --- how to connect from outside the house
        c = self._card(body, self.t("rm_howto_title"), **pad)
        ttk.Label(c, text=self.t("rm_howto"), wraplength=720, justify="left").pack(anchor="w")

        self._rm_fill_addresses()
        self._rm_show_mode()
        self._rm_render_client()
        if not getattr(self, "_rm_ticking", False):
            self._rm_ticking = True
            self.root.after(500, self._rm_tick)

    # ---- mode
    def _rm_on_mode(self) -> None:
        mode = self.rm_mode_var.get()
        if mode == self.config.remote_mode:
            return
        self.config.remote_mode = mode
        self.config.save()
        self.engine.apply_remote()
        self._rm_show_mode()

    def _rm_show_mode(self) -> None:
        self.rm_host.pack_forget()
        self.rm_client.pack_forget()
        if self.config.remote_mode == "host":
            self.rm_host.pack(fill="x")
            self._rm_render_code()
            self._rm_render_host()
        elif self.config.remote_mode == "client":
            self.rm_client.pack(fill="x")

    # ---- host
    def _rm_fill_addresses(self) -> None:
        self._rm_addresses = remote.local_addresses() or [("lan", "127.0.0.1")]
        labels = [f"{ip}  ({self.t('rm_kind_' + kind)})" for kind, ip in self._rm_addresses]
        self.rm_addr_combo.configure(values=labels)
        self.rm_addr_combo.current(0)
        has_ts = any(k == "tailscale" for k, _ in self._rm_addresses)
        self.rm_addr_note.configure(text=self.t("rm_addr_ts" if has_ts else "rm_addr_lan"))
        self._rm_render_code()

    def _rm_render_code(self) -> None:
        if not self.config.host_key or not getattr(self, "_rm_addresses", None):
            self.rm_code_var.set("")
            return
        ip = self._rm_addresses[max(self.rm_addr_combo.current(), 0)][1]
        self.rm_code_var.set(remote.make_code(ip, self.config.host_port, self.config.host_key))

    def _rm_copy_code(self) -> None:
        code = self.rm_code_var.get()
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.overlay.flash(self.t("rm_code_copied"))

    def _rm_new_key(self) -> None:
        if not messagebox.askyesno(self.t("rm_new_key"), self.t("rm_new_key_confirm"), parent=self.root,
                                   icon="warning"):
            return
        self.config.host_key = remote.new_key()
        self.config.save()
        self.engine.apply_remote()
        self._rm_render_code()

    def _rm_render_host(self) -> None:
        host = self.engine.host
        if host is None:
            self.rm_host_status.set(self.t("rm_host_off"))
            for var in self.rm_stat_vars.values():
                var.set("–")
            return
        tr_ = self.engine.transcriber
        model = self._label_for(tr_.source) if tr_ else self.t("none")
        where = self.t("rm_where_gpu") if tr_ is not None and tr_.device == "cuda" else self.t("rm_where_cpu")
        self.rm_host_status.set(self.t("rm_host_on", port=host.port, model=model, where=where))
        self.rm_stat_vars["rm_stat_now"].set(str(host.stats.active_count()))
        rows = host.stats.snapshot()
        self.rm_stat_vars["rm_stat_total"].set(str(len(rows)))
        self.rm_stat_vars["rm_stat_busy"].set(str(host.busy))
        sel = self.rm_tree.selection()
        self.rm_tree.delete(*self.rm_tree.get_children())
        for r in rows:
            self.rm_tree.insert("", "end", iid=r["id"], values=(
                r.get("name", "?"), r.get("ip", ""), self._rm_ago(r.get("last_seen", 0)),
                r.get("dictations", 0), r.get("rewrites", 0), f"{r.get('audio_s', 0) / 60:.1f}"))
        if sel and self.rm_tree.exists(sel[0]):
            self.rm_tree.selection_set(sel[0])

    def _rm_ago(self, ts: float) -> str:
        s = time.time() - ts
        if s < 60:
            return self.t("rm_now")
        if s < 3600:
            return self.t("rm_min_ago", n=int(s // 60))
        if s < 86400:
            return self.t("rm_h_ago", n=int(s // 3600))
        return time.strftime("%d/%m %H:%M", time.localtime(ts))

    def _rm_forget(self, all_: bool = False) -> None:
        host = self.engine.host
        if host is None:
            return
        if all_:
            host.stats.forget()
        else:
            sel = self.rm_tree.selection()
            if sel:
                host.stats.forget(sel[0])
        self._rm_render_host()

    def _rm_tick(self) -> None:
        try:
            if self._page == "remote" and self.config.remote_mode == "host" and self.root.winfo_viewable():
                self._rm_render_host()
        except tk.TclError:
            pass
        self.root.after(3000, self._rm_tick)

    # ---- client
    def _rm_connect(self) -> None:
        code = self.rm_paste_var.get().strip()
        try:
            url, key = remote.parse_code(code)
        except Exception:  # noqa: BLE001
            messagebox.showerror(self.t("rm_client_title"), self.t("rm_bad_code"), parent=self.root)
            return
        self.config.remote_url, self.config.remote_key = url, key
        self.config.remote_mode = "client"
        self.config.save()
        self.rm_paste_var.set("")
        self.rm_client_status.set(self.t("rm_testing"))
        self.engine.apply_remote()

    def _rm_test(self) -> None:
        if self.engine.remote is None:
            self._rm_render_client()
            return
        self.rm_client_status.set(self.t("rm_testing"))
        import threading

        threading.Thread(target=self.engine.check_remote, daemon=True).start()

    def _rm_disconnect(self) -> None:
        self.config.remote_url = self.config.remote_key = ""
        self.config.save()
        self.engine.apply_remote()

    def _rm_render_client(self) -> None:
        if not hasattr(self, "rm_client_status"):
            return
        if not self.config.remote_url:
            self.rm_client_status.set(self.t("rm_client_none"))
            return
        st = self.engine.remote_status
        if st is None:
            self.rm_client_status.set(self.t("rm_testing"))
        elif st[0]:
            info = st[1] if isinstance(st[1], dict) else {}
            where = self.t("rm_where_gpu") if info.get("device") == "cuda" else self.t("rm_where_cpu")
            model = self._label_for(info["model"]) if info.get("model") else "?"
            self.rm_client_status.set(self.t("rm_client_ok", name=info.get("name", "?"), model=model,
                                             where=where, ms=info.get("ms", "?")))
        else:
            err = str(st[1])
            key = "rm_client_badkey" if "bad_key" in err else "rm_client_down"
            self.rm_client_status.set(self.t(key, err=err[:160]))

    def _rm_on_event(self, kind: str, payload) -> None:
        if kind in ("remote_status", "remote_changed"):
            self._rm_render_client()
            if hasattr(self, "rm_host_status") and self.config.remote_mode == "host":
                self._rm_render_host()
            self._render_chips()
        elif kind == "remote_down":
            self._set_last(("rm_down_last", {}))
        elif kind == "host_error":
            messagebox.showerror(self.t("rm_host_title"), self.t("rm_host_error", err=str(payload)[:300]),
                                 parent=self.root)
            if hasattr(self, "rm_host_status"):
                self._rm_render_host()
