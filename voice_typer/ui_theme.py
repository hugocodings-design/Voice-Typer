"""Look & feel: Windows 11 style (sv-ttk), light/dark palettes, fonts and icon glyphs."""

import ctypes
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

import sv_ttk

# Bright green accent on soft, slightly green-tinted grays.
PALETTES = {
    "light": {
        "bg": "#fafafa", "sidebar": "#e8ebe9", "card": "#ffffff", "text": "#1a1d1b",
        "muted": "#5c6460", "accent": "#16a34a", "accent_fg": "#ffffff", "accent_soft": "#d9f5e1",
        "hover": "#dde2de", "border": "#d5dad6", "key_bg": "#ffffff", "key_border": "#c3cac5",
        "group_bg": "#e6f4ea", "ok": "#16a34a", "rec": "#dc2626", "busy": "#d97706", "off": "#9aa19c",
        "bright": "#22c55e",
    },
    "dark": {
        "bg": "#1c1c1c", "sidebar": "#141615", "card": "#242725", "text": "#eef1ef",
        "muted": "#9da5a0", "accent": "#4ade80", "accent_fg": "#052e16", "accent_soft": "#1d3526",
        "hover": "#232725", "border": "#343935", "key_bg": "#2a2e2b", "key_border": "#454b47",
        "group_bg": "#1f2e24", "ok": "#4ade80", "rec": "#f87171", "busy": "#fbbf24", "off": "#6f7672",
        "bright": "#4ade80",
    },
}

THEME_DIR = Path(__file__).resolve().parent / "theme"  # green Sun Valley (tools/make_theme.py)


def _load_theme(root: tk.Tk) -> None:
    if getattr(root, "_vt_theme_loaded", False):
        return
    if (THEME_DIR / "sv.tcl").exists():
        root.tk.call("source", str(THEME_DIR / "sv.tcl"))
    else:  # fallback: the original (blue) theme
        sv_ttk._load_theme(ttk.Style(root))
    root._vt_theme_loaded = True


ICONS = {  # Segoe Fluent Icons / Segoe MDL2 Assets code points
    "writing": "", "help": "",
    "home": "", "dictionary": "", "language": "", "models": "",
    "settings": "", "mic": "", "keyboard": "", "star": "",
    "star_filled": "", "remote": "", "gpu": "", "check": "", "add": "", "delete": "",
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
    _load_theme(root)
    ttk.Style(root).theme_use(f"sun-valley-{mode}")
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
