"""Small floating pill at the bottom of the screen while dictating.

It never takes focus and lets clicks through, so text still lands in the app you're using.
It stays mapped all the time and is shown/hidden by changing its opacity: re-showing a
window on Windows can steal focus, changing opacity cannot.
"""

import ctypes
import tkinter as tk
import tkinter.font as tkfont

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

KEY = "#010203"  # transparent color (outside the rounded pill)
BG = "#1e2120"        # charcoal gray
EDGE = "#353b37"      # thin outline: softens the pill's edge
FG = "#eef1ef"
GREEN = "#4ade80"     # bright green (recording, info)
GREEN_DIM = "#16a34a"
GRAY = "#c5cbc7"      # transcribing / AI writing
GRAY_DIM = "#6f7672"
WAVE_BG = "#272c29"   # the wave's own zone: the text never runs under it
BARS = 20


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
    W, H = 360, 52
    CAP_W = 640
    WAVE_W = 150          # wave zone on the right of the pill (recording only)
    TEXT_X = 46

    def __init__(self, root: tk.Tk, level_source):
        self.root = root
        self.level_source = level_source  # callable -> float
        self.state = "hidden"
        self._levels = [0.0] * BARS
        self._smooth = 0.0
        self._tick = 0
        self._font = tkfont.Font(root=root, family="Segoe UI", size=11, weight="bold")

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
        h = self.H - 1
        c.create_oval(0, 0, h, h, fill=BG, outline=EDGE, width=1)
        c.create_oval(self.W - 1 - h, 0, self.W - 1, h, fill=BG, outline=EDGE, width=1)
        c.create_rectangle(r, 0, self.W - 1 - r, h, fill=BG, outline="")
        c.create_line(r, 0, self.W - 1 - r, 0, fill=EDGE)
        c.create_line(r, h, self.W - 1 - r, h, fill=EDGE)
        self.halo = c.create_oval(13, r - 12, 37, r + 12, fill=BG, outline="")
        self.dot = c.create_oval(18, r - 7, 32, r + 7, fill=GREEN, outline="")
        self.text = c.create_text(self.TEXT_X, r, text="", fill=FG, anchor="w", font=self._font)
        # wave zone: a rounded, slightly lighter strip with symmetric rounded bars
        x0, x1 = self.W - self.WAVE_W - 10, self.W - 14
        y0, y1 = 9, self.H - 9
        rad = (y1 - y0) // 2
        self.wave_bg = [
            c.create_oval(x0, y0, x0 + 2 * rad, y1, fill=WAVE_BG, outline=""),
            c.create_oval(x1 - 2 * rad, y0, x1, y1, fill=WAVE_BG, outline=""),
            c.create_rectangle(x0 + rad, y0, x1 - rad, y1, fill=WAVE_BG, outline=""),
        ]
        step = (x1 - x0 - 2 * rad) / (BARS - 1)
        self._bar_x = [x0 + rad + i * step for i in range(BARS)]
        self._bar_max = (y1 - y0) / 2 - 4
        self.bars = [c.create_line(x, r, x, r, fill=GREEN, width=3, capstyle="round") for x in self._bar_x]
        self._show_wave(False)

        _click_through(top)

        # Live transcription caption, above the pill (same click-through, never-focused window)
        cap = self.caption = tk.Toplevel(root)
        cap.overrideredirect(True)
        # Position must be set before the first map, or later moves of this window are ignored.
        cap.geometry(f"{self.CAP_W}x40+{(sw - self.CAP_W) // 2}+{sh - self.H - 140}")
        cap.attributes("-topmost", True)
        cap.attributes("-alpha", 0.0)
        cap.configure(bg=BG, highlightthickness=1, highlightbackground=EDGE)
        tk.Frame(cap, bg=GREEN, width=4).pack(side="left", fill="y")  # green accent stripe
        self.caption_label = tk.Label(cap, text="", bg=BG, fg=FG, font=("Segoe UI", 12), justify="left",
                                      wraplength=self.CAP_W - 36, anchor="w", padx=14, pady=10)
        self.caption_label.pack(side="left", fill="both", expand=True)
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

    def _show_wave(self, on: bool) -> None:
        for item in self.wave_bg + self.bars:
            self.canvas.itemconfigure(item, state="normal" if on else "hidden")

    def fit(self, label: str, width: int) -> str:
        """The label cut with « … » so it fits in `width` pixels (never under the wave)."""
        if self._font.measure(label) <= width:
            return label
        while label and self._font.measure(label + "…") > width:
            label = label[:-1]
        return label.rstrip(" ·") + "…"

    def show(self, state: str, label: str) -> None:
        recording = state == "recording"
        room = (self.W - self.WAVE_W - 10 - 12 if recording else self.W - 24) - self.TEXT_X
        self.canvas.itemconfigure(self.text, text=self.fit(label, room))
        color = GRAY if state in ("transcribing",) else GREEN
        self.canvas.itemconfigure(self.dot, fill=color)
        self.canvas.itemconfigure(self.halo, fill=BG)
        if recording and self.state != "recording":
            self._levels = [0.0] * BARS
            self._smooth = 0.0
        self._show_wave(recording)
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
            raw = min(1.0, self.level_source() * 12) ** 0.7   # quiet speech still shows
            # rises at once, falls gently: a steady wave instead of flicker
            self._smooth = raw if raw > self._smooth else self._smooth * 0.8 + raw * 0.2
            self._levels = self._levels[1:] + [self._smooth]
            for i, b in enumerate(self.bars):
                # slightly taller in the middle of the strip, like a real waveform
                shape = 0.55 + 0.45 * (1 - abs(i - (BARS - 1) / 2) / ((BARS - 1) / 2))
                h = 1.5 + self._levels[i] * self._bar_max * shape
                x = self._bar_x[i]
                self.canvas.coords(b, x, r - h, x, r + h)
            on = (self._tick // 8) % 2 == 0
            self.canvas.itemconfigure(self.dot, fill=GREEN if on else GREEN_DIM)
            self.canvas.itemconfigure(self.halo, fill="#24402e" if on else BG)  # soft glow
        elif self.state == "transcribing":
            pulse = GRAY if (self._tick // 5) % 2 == 0 else GRAY_DIM
            self.canvas.itemconfigure(self.dot, fill=pulse)
        self.root.after(50, self._animate)
