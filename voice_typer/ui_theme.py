"""Look & feel: Windows 11 style (sv-ttk), light/dark palettes, fonts and icon glyphs."""

import ctypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import sv_ttk

PALETTES = {
    "light": {
        "bg": "#fafafa", "sidebar": "#f0f0f3", "card": "#ffffff", "text": "#1b1b1f",
        "muted": "#5f6368", "accent": "#2563eb", "accent_fg": "#ffffff", "accent_soft": "#e3ecfd",
        "hover": "#e4e4e9", "border": "#dcdce0", "key_bg": "#ffffff", "key_border": "#c8c8cf",
        "group_bg": "#eef2fb", "ok": "#1e8e3e", "rec": "#d93025", "busy": "#e37400", "off": "#9aa0a6",
    },
    "dark": {
        "bg": "#1c1c1c", "sidebar": "#202024", "card": "#2b2b2b", "text": "#f2f2f2",
        "muted": "#a8a8b0", "accent": "#5b9cff", "accent_fg": "#0b1220", "accent_soft": "#22324d",
        "hover": "#2d2d33", "border": "#3a3a40", "key_bg": "#323238", "key_border": "#4a4a52",
        "group_bg": "#26324a", "ok": "#5bd17b", "rec": "#ff6b5e", "busy": "#ffb347", "off": "#7a7a80",
    },
}

ICONS = {  # Segoe Fluent Icons / Segoe MDL2 Assets code points
    "writing": "",
    "home": "", "dictionary": "", "language": "", "models": "",
    "settings": "", "mic": "", "keyboard": "", "star": "",
    "star_filled": "", "gpu": "", "check": "", "add": "", "delete": "",
}


def system_prefers_dark() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def resolve_mode(setting: str) -> str:
    if setting in ("light", "dark"):
        return setting
    return "dark" if system_prefers_dark() else "light"


def _dark_title_bar(root: tk.Tk, dark: bool) -> None:
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11 / older Win10)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:  # noqa: BLE001 — cosmetic
        pass


class Fonts:
    def __init__(self, root: tk.Tk):
        families = set(tkfont.families(root))
        base = "Segoe UI Variable Text" if "Segoe UI Variable Text" in families else "Segoe UI"
        display = "Segoe UI Variable Display" if "Segoe UI Variable Display" in families else "Segoe UI"
        icons = "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"
        self.body = (base, 10)
        self.small = (base, 9)
        self.bold = (base, 10, "bold")
        self.nav = (base, 10)
        self.h1 = (display, 20, "bold")
        self.h2 = (display, 12, "bold")
        self.status = (display, 14, "bold")
        self.key = (base, 11, "bold")
        self.icon = (icons, 13)
        self.icon_small = (icons, 10)
        self.app = (display, 13, "bold")


def apply(root: tk.Tk, setting: str) -> tuple[str, dict]:
    mode = resolve_mode(setting)
    sv_ttk.set_theme(mode, root)
    pal = dict(PALETTES[mode])
    style = ttk.Style(root)
    # ttk widgets inside cards use the theme background: match plain tk widgets to it.
    pal["bg"] = style.lookup("TFrame", "background") or pal["bg"]
    pal["card"] = pal["bg"]
    style.configure("Treeview", rowheight=30)
    style.configure("Muted.TLabel", foreground=pal["muted"])
    style.configure("H1.TLabel", font=Fonts(root).h1)
    style.configure("H2.TLabel", font=Fonts(root).h2)
    _dark_title_bar(root, mode == "dark")
    return mode, pal
