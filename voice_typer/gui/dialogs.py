"""Pop-ups in the app's own look (green and gray, light or dark), replacing Windows' message boxes.

Same call style as tkinter.messagebox / simpledialog, so modules simply import this instead:
    from voice_typer.gui import dialogs as messagebox
"""

import ctypes
import tkinter as tk
from tkinter import ttk

from voice_typer import ui_theme

_theme = {"mode": "light", "pal": ui_theme.PALETTES["light"], "fonts": None, "lang": "fr"}
_last = None  # last dialog opened (used by screenshot tests)

LABELS = {
    "fr": {"ok": "OK", "yes": "Oui", "no": "Non", "cancel": "Annuler"},
    "en": {"ok": "OK", "yes": "Yes", "no": "No", "cancel": "Cancel"},
}
# kind -> (Segoe Fluent glyph, colour key, soft background) per mode
KINDS = {
    "info": ("", "accent", {"light": "#d9f5e1", "dark": "#1d3526"}),
    "question": ("", "accent", {"light": "#d9f5e1", "dark": "#1d3526"}),
    "warning": ("", "busy", {"light": "#fdecc8", "dark": "#3d3016"}),
    "error": ("", "rec", {"light": "#fde2e2", "dark": "#3f1d1d"}),
}


def configure(mode: str, pal: dict, fonts, lang: str) -> None:
    """Called by the main window whenever the theme or interface language changes."""
    _theme.update(mode=mode, pal=pal, fonts=fonts, lang=lang if lang in LABELS else "en")


def _fonts(root):
    if _theme["fonts"] is None:
        _theme["fonts"] = ui_theme.Fonts(root)
    return _theme["fonts"]


def _dark_title_bar(win: tk.Toplevel) -> None:
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        value = ctypes.c_int(1 if _theme["mode"] == "dark" else 0)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:  # noqa: BLE001 — cosmetic
        pass


def _dialog(kind: str, title: str, message: str, buttons: list[tuple[str, object, bool]],
            parent=None, entry: str | None = None):
    """buttons: (label key, value returned, is_primary). Escape returns the last button's value."""
    global _last
    root = parent or tk._default_root
    pal, mode = _theme["pal"], _theme["mode"]
    fonts = _fonts(root)
    labels = LABELS[_theme["lang"]]
    result = {"value": buttons[-1][1]}

    win = _last = tk.Toplevel(root)
    win.withdraw()
    win.title(title)
    win.resizable(False, False)
    try:
        owner = (parent or root).winfo_toplevel()
        if owner.winfo_viewable():  # a dialog owned by a hidden window would stay hidden too
            win.transient(owner)
    except Exception:  # noqa: BLE001
        pass

    body = ttk.Frame(win, padding=(24, 22, 24, 18))
    body.pack(fill="both", expand=True)
    glyph, color_key, soft = KINDS[kind]
    badge = tk.Canvas(body, width=44, height=44, highlightthickness=0, bg=pal["bg"])
    badge.create_oval(1, 1, 43, 43, fill=soft[mode], outline="")
    badge.create_text(22, 22, text=glyph, fill=pal[color_key], font=(fonts.icon[0], 17))
    badge.grid(row=0, column=0, rowspan=3, sticky="n", padx=(0, 16))
    ttk.Label(body, text=title, font=fonts.h2).grid(row=0, column=1, sticky="w")
    ttk.Label(body, text=message, wraplength=400, justify="left").grid(row=1, column=1, sticky="w", pady=(6, 0))
    var = None
    if entry is not None:
        var = tk.StringVar(value=entry)
        field = ttk.Entry(body, textvariable=var, width=44)
        field.grid(row=2, column=1, sticky="ew", pady=(12, 0))
        field.select_range(0, "end")

    footer = tk.Frame(win, bg=pal["sidebar"], padx=20, pady=12)
    footer.pack(fill="x")
    tk.Frame(win, bg=pal["border"], height=1).place(in_=footer, relx=0, rely=0, relwidth=1)

    def close(value):
        result["value"] = value
        if var is not None and value is not None:
            result["value"] = var.get()
        win.grab_release()
        win.destroy()

    primary = None
    for key, value, is_primary in reversed(buttons):  # packed right-to-left: primary ends up rightmost
        b = ttk.Button(footer, text=labels[key], style="Accent.TButton" if is_primary else "TButton",
                       command=lambda v=value: close(v), width=10)
        b.pack(side="right", padx=(8, 0))
        if is_primary:
            primary = (b, value)
    win.bind("<Escape>", lambda e: close(buttons[-1][1]))
    if primary:
        win.bind("<Return>", lambda e: close(primary[1]))
    win.protocol("WM_DELETE_WINDOW", lambda: close(buttons[-1][1]))

    # centre over the parent window (or the screen)
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    try:
        top = (parent or root).winfo_toplevel()
        if top.winfo_viewable():
            x = top.winfo_rootx() + (top.winfo_width() - w) // 2
            y = top.winfo_rooty() + (top.winfo_height() - h) // 3
        else:
            raise ValueError
    except Exception:  # noqa: BLE001
        x, y = (win.winfo_screenwidth() - w) // 2, (win.winfo_screenheight() - h) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.deiconify()
    _dark_title_bar(win)
    win.lift()
    try:
        win.grab_set()
    except tk.TclError:
        pass
    (field if entry is not None else (primary[0] if primary else win)).focus_set()
    win.wait_window()
    return result["value"]


def showinfo(title, message, parent=None, **_):
    return _dialog("info", title, message, [("ok", "ok", True)], parent)


def showwarning(title, message, parent=None, **_):
    return _dialog("warning", title, message, [("ok", "ok", True)], parent)


def showerror(title, message, parent=None, **_):
    return _dialog("error", title, message, [("ok", "ok", True)], parent)


def askyesno(title, message, parent=None, icon=None, **_):
    kind = "warning" if icon == "warning" else "question"
    return bool(_dialog(kind, title, message, [("yes", True, True), ("no", False, False)], parent))


def askstring(title, prompt, parent=None, initialvalue="", **_):
    value = _dialog("question", title, prompt, [("ok", True, True), ("cancel", None, False)], parent,
                    entry=initialvalue or "")
    return value if isinstance(value, str) else None
