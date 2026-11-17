"""Floating microphone button — the PC version of Voice Typer Mobile's bubble.

Click = start dictating, click again = stop (whatever the shortcut mode). Right-click = menu: dictate with
another preset, always use a preset in this application, language, re-paste / undo the last dictation,
hide the button. Right-click while dictating = cancel. Drag it anywhere; its position is remembered.

The window never takes focus (WS_EX_NOACTIVATE), so the text still lands in the application you were
typing in. Like the overlay, it stays mapped and is shown/hidden through its opacity (re-showing a window
can steal focus). The menu does take focus while open: the previous window is put back in front before
the chosen action runs.
"""

import ctypes
import tkinter as tk

from voice_typer import languages

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

KEY = "#010203"       # transparent colour around the round button
GREEN = "#16a34a"
GREEN_EDGE = "#4ade80"
RED = "#dc2626"
GRAY = "#6b7280"
FG = "#ffffff"
SIZE = 56
DRAG_PX = 4


def _no_activate(win: tk.Toplevel) -> None:
    win.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
    except Exception:  # noqa: BLE001 — not on Windows (tests): cosmetic only
        pass


def _foreground() -> int:
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:  # noqa: BLE001
        return 0


def _restore_foreground(hwnd: int) -> None:
    if hwnd:
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:  # noqa: BLE001
            pass


def _cursor() -> tuple[int, int] | None:
    try:
        from ctypes import wintypes

        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    except Exception:  # noqa: BLE001
        return None


class MicButton:
    def __init__(self, window):
        self.window = window            # gui.window.Window (engine, config, t(), _show_window)
        self.root: tk.Tk = window.root
        self.engine = window.engine
        self.config = window.config
        self.shown = False
        self.menu_open = False
        self._rect = (0, 0, 0, 0)       # screen rectangle, read from the mouse-hook thread
        self._press = None              # (x_root, y_root, win_x, win_y) at button press
        self._dragged = False
        self._tick = 0

        top = self.top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.0)
        top.configure(bg=KEY)
        top.attributes("-transparentcolor", KEY)
        x, y = self._initial_position()
        top.geometry(f"{SIZE}x{SIZE}+{x}+{y}")
        c = self.canvas = tk.Canvas(top, width=SIZE, height=SIZE, bg=KEY, highlightthickness=0, cursor="hand2")
        c.pack()
        self.ring = c.create_oval(1, 1, SIZE - 2, SIZE - 2, outline="", width=3)
        self.disc = c.create_oval(5, 5, SIZE - 6, SIZE - 6, fill=GREEN, outline=GREEN_EDGE, width=1)
        icon_font = getattr(window, "fonts", None)
        family = icon_font.icon[0] if icon_font else "Segoe MDL2 Assets"
        self.glyph = c.create_text(SIZE // 2, SIZE // 2 - 6, text="", fill=FG, font=(family, 16))
        self.badge = c.create_text(SIZE // 2, SIZE // 2 + 14, text="", fill=FG, font=("Segoe UI", 8, "bold"))
        for seq, fn in (("<ButtonPress-1>", self._on_press), ("<B1-Motion>", self._on_drag),
                        ("<ButtonRelease-1>", self._on_release), ("<Button-3>", self._on_right)):
            c.bind(seq, fn)
        _no_activate(top)
        self.engine.undo.ignore_click = self.owns_click
        self._loop()

    # ------------------------------------------------------------------ placement
    def _initial_position(self) -> tuple[int, int]:
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        pos = self.config.mic_button_pos
        if isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) for v in pos):
            # keep it reachable if the screen got smaller (laptop undocked…)
            return max(0, min(pos[0], sw - SIZE)), max(0, min(pos[1], sh - SIZE))
        return sw - SIZE - 24, int(sh * 0.62)

    def _update_rect(self) -> None:
        x, y = self.top.winfo_x(), self.top.winfo_y()
        self._rect = (x, y, x + SIZE, y + SIZE)

    def owns_click(self) -> bool:
        """Called from the mouse-hook thread: is this click on the button or its menu?"""
        if self.menu_open:
            return True
        if not self.shown:
            return False
        p = _cursor()
        x0, y0, x1, y1 = self._rect
        return p is not None and x0 <= p[0] < x1 and y0 <= p[1] < y1

    # ------------------------------------------------------------------ show / hide
    def show(self) -> None:
        if not self.shown:
            self.top.attributes("-alpha", 0.95)
            self.top.attributes("-topmost", True)
            self.shown = True
            self._update_rect()

    def hide(self) -> None:
        self.top.attributes("-alpha", 0.0)
        self.shown = False

    def sync(self) -> None:
        """Follow the setting (Réglages)."""
        self.show() if self.config.mic_button else self.hide()

    # ------------------------------------------------------------------ mouse
    def _on_press(self, e) -> None:
        self._press = (e.x_root, e.y_root, self.top.winfo_x(), self.top.winfo_y())
        self._dragged = False

    def _on_drag(self, e) -> None:
        if not self._press:
            return
        x0, y0, wx, wy = self._press
        dx, dy = e.x_root - x0, e.y_root - y0
        if not self._dragged and abs(dx) <= DRAG_PX and abs(dy) <= DRAG_PX:
            return
        self._dragged = True
        self.top.geometry(f"+{wx + dx}+{wy + dy}")

    def _on_release(self, _e) -> None:
        if self._dragged:
            self.top.update_idletasks()
            self._update_rect()
            self.config.mic_button_pos = [self.top.winfo_x(), self.top.winfo_y()]
            self.config.save()
        elif self._press:
            self.engine.button_dictate()
        self._press = None
        self._dragged = False

    def _on_right(self, e) -> None:
        if self.engine.recorder.is_recording:
            self.engine.cancel_recording()  # like Esc / a long press on the phone
            return
        self._show_menu(e.x_root, e.y_root)

    # ------------------------------------------------------------------ menu
    def _show_menu(self, x: int, y: int) -> None:
        from voice_typer.winapp import foreground_exe, friendly

        t = self.window.t
        target_hwnd = _foreground()
        try:
            exe = foreground_exe()
        except Exception:  # noqa: BLE001
            exe = ""
        presets = self.config.presets or []
        current = self.engine.preset_for_app(exe) if exe else None

        def then(action):
            """Run a menu action once the application the user was in is back in front."""
            def run():
                _restore_foreground(target_hwnd)
                self.root.after(120, action)
            return run

        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=t("mb_dictate_with"), state="disabled")
        m.add_command(label=t("mb_plain"), command=then(lambda: self.engine.button_dictate(None, use_app_preset=False)))
        for p in presets:
            mark = "  ✓" if p.get("id") == current else ""
            m.add_command(label=f"{p.get('name', '?')}{mark}",
                          command=then(lambda pid=p.get("id"): self.engine.button_dictate(pid)))
        if exe:
            sub = tk.Menu(m, tearoff=0)
            choice = tk.StringVar(master=m, value=current or "")
            sub.add_radiobutton(label=t("mb_no_preset"), variable=choice, value="",
                                command=lambda: self.engine.set_app_preset(exe, None))
            for p in presets:
                sub.add_radiobutton(label=p.get("name", "?"), variable=choice, value=p.get("id"),
                                    command=lambda pid=p.get("id"): self.engine.set_app_preset(exe, pid))
            m.add_separator()
            m.add_cascade(label=t("mb_always_in", app=friendly(exe)), menu=sub)
        lang = tk.Menu(m, tearoff=0)
        lang_var = tk.StringVar(master=m, value=self.config.language or "")
        lang.add_radiobutton(label=languages.name(None, self.config.ui_language), variable=lang_var, value="",
                             command=lambda: self.engine.set_language(None))
        for code in languages.SUPPORTED:
            lang.add_radiobutton(label=languages.name(code, self.config.ui_language), variable=lang_var, value=code,
                                 command=lambda c=code: self.engine.set_language(c))
        m.add_cascade(label=t("mb_language", lang=languages.short(self.config.language)), menu=lang)
        m.add_separator()
        m.add_command(label=t("mb_repaste"), state="normal" if self.engine.last_text else "disabled",
                      command=then(self.engine.paste_last))
        m.add_command(label=t("mb_undo"), command=then(self.engine.undo_last))
        m.add_separator()
        m.add_command(label=t("mb_open"), command=self.window._show_window)
        m.add_command(label=t("mb_hide"), command=self._hide_from_menu)

        self.menu_open = True
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()
            # tk_popup returns when the menu closes; the click that closed it is still in flight
            self.root.after(400, lambda: setattr(self, "menu_open", False))

    def _hide_from_menu(self) -> None:
        self.config.mic_button = False
        self.config.save()
        self.hide()
        self.window.overlay.flash(self.window.t("mb_hidden"), ms=3500)

    # ------------------------------------------------------------------ animation
    def _loop(self) -> None:
        self._tick += 1
        if self.shown:
            c = self.canvas
            if self.engine.recorder.is_recording:
                level = min(1.0, self.engine.recorder.level * 12)
                c.itemconfigure(self.disc, fill=RED, outline=RED)
                c.itemconfigure(self.ring, outline=RED if level > 0.08 else "")
                pad = 3 - int(2 * level)
                c.coords(self.ring, pad, pad, SIZE - 1 - pad, SIZE - 1 - pad)
                c.itemconfigure(self.badge, text="")
            elif getattr(self.engine, "busy", False):
                c.itemconfigure(self.disc, fill=GRAY if (self._tick // 5) % 2 == 0 else "#4b5563", outline=GRAY)
                c.itemconfigure(self.ring, outline="")
                c.itemconfigure(self.badge, text="…")
            else:
                c.itemconfigure(self.disc, fill=GREEN, outline=GREEN_EDGE)
                c.itemconfigure(self.ring, outline="")
                c.itemconfigure(self.badge, text=languages.short(self.config.language))
        self.root.after(60, self._loop)
