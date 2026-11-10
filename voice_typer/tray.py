"""Icon next to the Windows clock (pystray), so the app keeps running when the window is closed."""

from collections.abc import Callable

from PIL import Image, ImageDraw

try:
    import pystray
except Exception:  # noqa: BLE001
    pystray = None


def _icon_image(color: str = "#1a73e8") -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=color)
    d.rounded_rectangle((24, 12, 40, 38), radius=8, fill="white")      # mic head
    d.arc((17, 22, 47, 46), start=0, end=180, fill="white", width=4)   # mic cradle
    d.line((32, 46, 32, 53), fill="white", width=4)
    d.line((24, 53, 40, 53), fill="white", width=4)
    return img


class Tray:
    def __init__(self, labels: dict[str, str], on_open: Callable[[], None], on_quit: Callable[[], None]):
        self.icon = None
        if pystray is None:
            return
        menu = pystray.Menu(
            pystray.MenuItem(labels["open"], lambda: on_open(), default=True),
            pystray.MenuItem(labels["quit"], lambda: on_quit()),
        )
        self.icon = pystray.Icon("VoiceTyper", _icon_image(), "Voice Typer", menu)

    @property
    def available(self) -> bool:
        return self.icon is not None

    def start(self) -> None:
        if self.icon:
            self.icon.run_detached()

    def set_recording(self, recording: bool) -> None:
        if self.icon:
            self.icon.icon = _icon_image("#d93025" if recording else "#1a73e8")

    def notify(self, message: str) -> None:
        if self.icon:
            try:
                self.icon.notify(message, "Voice Typer")
            except Exception:  # noqa: BLE001
                pass

    def stop(self) -> None:
        if self.icon:
            self.icon.stop()
