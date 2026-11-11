"""Small floating pill at the bottom of the screen while dictating.

It never takes focus and lets clicks through, so text still lands in the app you're using.
It stays mapped all the time and is shown/hidden by changing its opacity: re-showing a
window on Windows can steal focus, changing opacity cannot.
"""

import ctypes
import tkinter as tk

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

KEY = "#010203"  # transparent color (outside the rounded pill)
BG = "#202124"
FG = "#f1f3f4"
RED = "#ea4335"
AMBER = "#fbbc04"
BLUE = "#5b9cff"
BARS = 14


def _click_through(win: tk.Toplevel) -> None:
    win.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        )
    except Exception:  # noqa: BLE001 — cosmetic only
        pass


class Overlay:
    W, H = 260, 50
    CAP_W = 640

    def __init__(self, root: tk.Tk, level_source):
        self.root = root
        self.level_source = level_source  # callable -> float
        self.state = "hidden"
        self._levels = [0.0] * BARS
        self._tick = 0

        top = self.top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.0)
        top.configure(bg=KEY)
        top.attributes("-transparentcolor", KEY)
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        top.geometry(f"{self.W}x{self.H}+{(sw - self.W) // 2}+{sh - self.H - 80}")

        c = self.canvas = tk.Canvas(top, width=self.W, height=self.H, bg=KEY, highlightthickness=0)
        c.pack()
        r = self.H // 2
        c.create_oval(0, 0, self.H, self.H, fill=BG, outline=BG)
        c.create_oval(self.W - self.H, 0, self.W, self.H, fill=BG, outline=BG)
        c.create_rectangle(r, 0, self.W - r, self.H, fill=BG, outline=BG)
        self.dot = c.create_oval(18, r - 7, 32, r + 7, fill=RED, outline="")
        self.text = c.create_text(44, r, text="", fill=FG, anchor="w", font=("Segoe UI", 11, "bold"))
        x0 = 150
        self.bars = [
            c.create_rectangle(x0 + i * 7, r, x0 + i * 7 + 4, r, fill=FG, outline="") for i in range(BARS)
        ]

        _click_through(top)

        # Live transcription caption, above the pill (same click-through, never-focused window)
        cap = self.caption = tk.Toplevel(root)
        cap.overrideredirect(True)
        # Position must be set before the first map, or later moves of this window are ignored.
        cap.geometry(f"{self.CAP_W}x40+{(sw - self.CAP_W) // 2}+{sh - self.H - 140}")
        cap.attributes("-topmost", True)
        cap.attributes("-alpha", 0.0)
        cap.configure(bg=BG)
        self.caption_label = tk.Label(cap, text="", bg=BG, fg=FG, font=("Segoe UI", 12), justify="left",
                                      wraplength=self.CAP_W - 32, anchor="w", padx=16, pady=10)
        self.caption_label.pack(fill="both", expand=True)
        self._caption_shown = False
        _click_through(cap)

    def flash(self, label: str, ms: int = 1300) -> None:
        """Briefly show an info message (e.g. the new language), unless dictation is in progress."""
        if self.state not in ("hidden", "info"):
            return
        self.show("info", label)
        self._flash_id = getattr(self, "_flash_id", 0) + 1
        fid = self._flash_id
        self.root.after(ms, lambda: self.hide() if self.state == "info" and self._flash_id == fid else None)

    def show(self, state: str, label: str) -> None:
        self.canvas.itemconfigure(self.text, text=label)
        color = {"recording": RED, "info": BLUE}.get(state, AMBER)
        self.canvas.itemconfigure(self.dot, fill=color)
        for b in self.bars:
            self.canvas.itemconfigure(b, state="normal" if state == "recording" else "hidden")
        if self.state == "hidden":
            self.top.attributes("-alpha", 0.94)
            self.top.attributes("-topmost", True)
        was_hidden = self.state == "hidden"
        self.state = state
        if was_hidden:
            self._animate()

    def hide(self) -> None:
        self.state = "hidden"
        self.top.attributes("-alpha", 0.0)
        self.hide_live()

    def set_live(self, text: str) -> None:
        """Show the live transcription above the pill (last ~3 lines)."""
        if len(text) > 260:
            text = "…" + text[-260:].split(" ", 1)[-1]
        self.caption_label.configure(text=text)
        cap = self.caption
        cap.update_idletasks()
        h = self.caption_label.winfo_reqheight()
        sw, sh = cap.winfo_screenwidth(), cap.winfo_screenheight()
        cap.geometry(f"{self.CAP_W}x{h}+{(sw - self.CAP_W) // 2}+{sh - self.H - 80 - h - 10}")
        if not self._caption_shown:
            cap.attributes("-alpha", 0.92)
            cap.attributes("-topmost", True)
            self._caption_shown = True

    def hide_live(self) -> None:
        if self._caption_shown:
            self.caption.attributes("-alpha", 0.0)
            self._caption_shown = False
            self.caption_label.configure(text="")

    def _animate(self) -> None:
        if self.state == "hidden":
            return
        self._tick += 1
        r = self.H // 2
        if self.state == "recording":
            level = min(1.0, self.level_source() * 12)
            self._levels = self._levels[1:] + [level]
            x0 = 150
            for i, b in enumerate(self.bars):
                h = 2 + self._levels[i] * (r - 8)
                self.canvas.coords(b, x0 + i * 7, r - h, x0 + i * 7 + 4, r + h)
            pulse = RED if (self._tick // 8) % 2 == 0 else "#b3261e"
            self.canvas.itemconfigure(self.dot, fill=pulse)
        elif self.state == "transcribing":
            pulse = AMBER if (self._tick // 5) % 2 == 0 else "#c99400"
            self.canvas.itemconfigure(self.dot, fill=pulse)
        self.root.after(50, self._animate)
