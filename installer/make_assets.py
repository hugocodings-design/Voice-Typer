"""Draws the app icon (.ico) and the installer wizard images (.bmp) into installer/build_assets.

Run by build.ps1; nothing here needs editing for a new version.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voice_typer.tray import BRAND, _icon_image  # noqa: E402

OUT = Path(__file__).resolve().parent / "build_assets"
TOP, BOTTOM = (42, 47, 44), (22, 25, 23)  # charcoal gray gradient (app grays)
GREEN = (74, 222, 128)  # bright green (app accent, dark mode)
FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


def gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line((0, y, w, y), fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))
    return img


def side_image(scale: float) -> Image.Image:
    """Left panel of the welcome / finish pages (164:314 ratio; 202x386 at 100 % since Inno Setup 6.6)."""
    w, h = round(164 * scale), round(314 * scale)
    img = gradient(w, h)
    # soft green glows
    deco = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    dd.ellipse((-0.45 * w, 0.62 * h, 0.75 * w, 1.25 * h), fill=GREEN + (16,))
    dd.ellipse((0.45 * w, -0.18 * h, 1.4 * w, 0.32 * h), fill=GREEN + (12,))
    img.paste(deco, (0, 0), deco)
    badge = _icon_image(BRAND, round(76 * scale))  # the app icon: green disc, white microphone
    bx = (w - badge.size[0]) // 2
    by = round(82 * scale)
    img.paste(badge, (bx, by), badge)
    d = ImageDraw.Draw(img)
    title = font("segoeuib.ttf", round(19 * scale))
    sub = font("segoeui.ttf", round(10.5 * scale))
    y = by + badge.size[1] + round(18 * scale)
    for text, f, col, gap in (("Voice Typer", title, (238, 241, 239), 8),
                              ("Dictée vocale", sub, GREEN, 2),
                              ("100 % locale et privée", sub, (157, 165, 160), 0)):
        tw = d.textlength(text, font=f)
        d.text(((w - tw) / 2, y), text, font=f, fill=col)
        y += f.size + round(gap * scale) + round(4 * scale)
    return img


def small_image(size: int) -> Image.Image:
    """Top-right corner of the inner pages (transparent, so it suits light and dark mode)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    badge = _icon_image(BRAND, round(size * 0.86))
    o = (size - badge.size[0]) // 2
    img.paste(badge, (o, o), badge)
    return img


VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040c04b0', [
      StringStruct('CompanyName', 'Voice Typer'),
      StringStruct('FileDescription', 'Voice Typer - dictée vocale locale'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'Voice Typer'),
      StringStruct('OriginalFilename', 'Voice Typer.exe'),
      StringStruct('ProductName', 'Voice Typer'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])]
)
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    big = _icon_image(size=256)
    big.save(OUT / "app.ico", sizes=[(s, s) for s in sizes])
    # Image-area sizes of Inno Setup 6.6+ at 100/125/150/175/200/225/250 % (Setup picks the closest).
    for f in OUT.glob("wizard_*.bmp"):
        f.unlink()
    for f in OUT.glob("small_*.png"):
        f.unlink()
    for i, width in enumerate((202, 269, 336, 403, 430, 498, 534)):
        side_image(width / 164).save(OUT / f"wizard_{i}.bmp")
    for i, size in enumerate((58, 77, 97, 116, 124, 143, 159)):
        small_image(size).save(OUT / f"small_{i}.png")
    from voice_typer import __version__

    nums = tuple(int(x) for x in (__version__.split(".") + ["0"] * 4)[:4])
    (OUT / "version_info.txt").write_text(VERSION_INFO.format(t=nums, v=__version__), encoding="utf-8")
    print("assets ->", OUT, "version", __version__)


if __name__ == "__main__":
    main()
