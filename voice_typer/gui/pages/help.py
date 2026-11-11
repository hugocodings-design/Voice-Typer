"""Page Aide & commandes: every voice command and keyboard shortcut in one place."""

import tkinter as tk
from tkinter import ttk

from voice_typer import commands
from voice_typer.gui.common import ScrollFrame


class HelpPage:
    def _page_help(self, page: ttk.Frame) -> None:
        self._page_header(page, "help")
        scroll = ScrollFrame(page, self.pal["bg"])
        scroll.pack(fill="both", expand=True)
        body = scroll.inner
        pad = {"padx": (0, 14)}

        # --- voice commands
        c = self._card(body, self.t("help_voice_title"), self.t("help_voice_sub"), **pad)
        self.voice_cmd_var = tk.BooleanVar(value=self.config.voice_commands)
        ttk.Checkbutton(c, text=self.t("help_voice_enable"), style="Switch.TCheckbutton",
                        variable=self.voice_cmd_var, command=self._on_voice_commands).pack(anchor="w", pady=(0, 10))
        rows = commands.reference(self.config.ui_language)
        tree = ttk.Treeview(c, columns=("say", "get"), show="headings", height=len(rows), selectmode="none")
        tree.heading("say", text=self.t("help_col_say"), anchor="w")
        tree.heading("get", text=self.t("help_col_get"), anchor="w")
        tree.column("say", width=500, anchor="w")
        tree.column("get", width=220, anchor="w")
        for say, get in rows:
            tree.insert("", "end", values=(say, get))
        tree.pack(fill="x")
        ttk.Label(c, text=self.t("help_voice_example"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(10, 0))

        # --- keyboard shortcuts (live from the settings)
        c = self._card(body, self.t("help_keys_title"), self.t("help_keys_sub"), **pad)
        grid = ttk.Frame(c)
        grid.pack(fill="x")
        rows = [(self.config.hotkey, self.t("help_key_dictate")),
                ("esc", self.t("help_key_esc"))]
        rows += [(p["hotkey"], self.t("help_key_preset", name=p["name"]))
                 for p in self.config.presets or [] if p.get("hotkey")]
        rows += [(self.config.rewrite_hotkey, self.t("help_key_rewrite")),
                 (self.config.paste_last_hotkey, self.t("help_key_paste")),
                 (self.config.language_hotkey, self.t("help_key_lang"))]
        for i, (combo, what) in enumerate(rows):
            self._keycaps(grid, combo).grid(row=i, column=0, sticky="w", pady=4)
            ttk.Label(grid, text=what).grid(row=i, column=1, sticky="w", padx=18, pady=4)
        ttk.Label(c, text=self.t("help_keys_note"), style="Muted.TLabel", wraplength=680,
                  justify="left").pack(anchor="w", pady=(10, 0))

    def _on_voice_commands(self) -> None:
        self.config.voice_commands = self.voice_cmd_var.get()
        self.config.save()
