"""Icon next to the Windows clock (pystray), so the app keeps running when the window is closed."""

from collections.abc import Callable

from PIL import Image, ImageDraw

try:
    import pystray
except Exception:  # noqa: BLE001
    pystray = None


BRAND = "#22c55e"  # bright green (see ui_theme.PALETTES)


def _icon_image(color: str = BRAND, size: int = 64) -> Image.Image:
    """Round microphone badge, drawn 4x larger then scaled down for smooth edges."""
    k = size * 4 / 64
    img = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def r(*xy):
        return tuple(round(v * k) for v in xy)

    d.ellipse(r(2, 2, 62, 62), fill=color)
    d.rounded_rectangle(r(24, 12, 40, 38), radius=round(8 * k), fill="white")      # mic head
    d.arc(r(17, 22, 47, 46), start=0, end=180, fill="white", width=round(4 * k))   # mic cradle
    d.line(r(32, 46, 32, 53), fill="white", width=round(4 * k))
    d.line(r(24, 53, 40, 53), fill="white", width=round(4 * k))
    return img.resize((size, size), Image.LANCZOS)


class Tray:
    """`build_menu(pystray)` returns the menu; call refresh() when its content changes."""

    def __init__(self, build_menu: Callable):
        self.icon = None
        self._build_menu = build_menu
        if pystray is None:
            return
        self.icon = pystray.Icon("VoiceTyper", _icon_image(), "Voice Typer", build_menu(pystray))

    @property
    def available(self) -> bool:
        return self.icon is not None

    def start(self) -> None:
        if self.icon:
            self.icon.run_detached()

    def refresh(self) -> None:
        if self.icon:
            self.icon.menu = self._build_menu(pystray)
            try:
                self.icon.update_menu()
            except Exception:  # noqa: BLE001
                pass

    def set_recording(self, recording: bool) -> None:
        if self.icon:
            self.icon.icon = _icon_image("#dc2626" if recording else BRAND)

    def notify(self, message: str) -> None:
        if self.icon:
            try:
                self.icon.notify(message, "Voice Typer")
            except Exception:  # noqa: BLE001
                pass

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:  # noqa: BLE001
                pass
