"""Shared constants and widgets for the window."""

import tkinter as tk
from tkinter import ttk

UI_LANGUAGES = [("fr", "Français"), ("en", "English")]
THEMES = ["system", "light", "dark"]
PRESETS = ["f9", "right ctrl", "ctrl+windows", "ctrl+alt+space"]
LANG_PRESETS = ["f8", "ctrl+alt+l", "ctrl+shift+l"]
PAGES = [("home", "home"), ("dictionary", "dictionary"), ("languages", "language"),
         ("models", "models"), ("writing", "writing"), ("remote", "remote"), ("help", "help"),
         ("settings", "settings")]
PASTE_PRESETS = ["f9", "f10", "ctrl+shift+v", "insert"]
REWRITE_PRESETS = ["f8", "f10", "ctrl+alt+r", "ctrl+shift+e"]
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

