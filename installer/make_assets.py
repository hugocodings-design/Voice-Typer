"""Draws the app icon (.ico) and the installer wizard images (.bmp) into installer/build_assets.

Run by build.ps1; nothing here needs editing for a new version.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voice_typer.tray import _icon_image  # noqa: E402

OUT = Path(__file__).resolve().parent / "build_assets"
TOP, BOTTOM = (30, 64, 175), (59, 130, 246)  # deep blue -> app accent blue
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
    """Left panel of the welcome / finish pages (164x314 at 100 %)."""
    w, h = round(164 * scale), round(314 * scale)
    img = gradient(w, h)
    # soft decorative circles
    deco = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    dd.ellipse((-0.45 * w, 0.62 * h, 0.75 * w, 1.25 * h), fill=(255, 255, 255, 18))
    dd.ellipse((0.45 * w, -0.18 * h, 1.4 * w, 0.32 * h), fill=(255, 255, 255, 14))
    img.paste(deco, (0, 0), deco)
    badge = _icon_image("#ffffff", round(76 * scale))
    # invert the badge: white disc with a blue microphone
    blue = Image.new("RGBA", badge.size, TOP + (255,))
    disc = badge.split()[3]
    mic = _icon_image("#000000", badge.size[0]).convert("L")
    mic = mic.point(lambda v: 255 if v > 128 else 0)
    badge = Image.composite(blue, Image.new("RGBA", badge.size, (255, 255, 255, 255)), mic)
    badge.putalpha(disc)
    bx = (w - badge.size[0]) // 2
    by = round(82 * scale)
    img.paste(badge, (bx, by), badge)
    d = ImageDraw.Draw(img)
    title = font("segoeuib.ttf", round(19 * scale))
    sub = font("segoeui.ttf", round(10.5 * scale))
    y = by + badge.size[1] + round(18 * scale)
    for text, f, col, gap in (("Voice Typer", title, (255, 255, 255), 8),
                              ("Dictée vocale", sub, (219, 234, 254), 2),
                              ("100 % locale et privée", sub, (219, 234, 254), 0)):
        tw = d.textlength(text, font=f)
        d.text(((w - tw) / 2, y), text, font=f, fill=col)
        y += f.size + round(gap * scale) + round(4 * scale)
    return img


def small_image(size: int) -> Image.Image:
    """Top-right corner of the inner pages (transparent, so it suits light and dark mode)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    badge = _icon_image("#2563eb", round(size * 0.86))
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
    for i, scale in enumerate((1, 1.25, 1.5, 1.75, 2)):
        side_image(scale).save(OUT / f"wizard_{i}.bmp")
    for i, size in enumerate((55, 69, 83, 97, 110, 138)):
        small_image(size).save(OUT / f"small_{i}.png")
    from voice_typer import __version__

    nums = tuple(int(x) for x in (__version__.split(".") + ["0"] * 4)[:4])
    (OUT / "version_info.txt").write_text(VERSION_INFO.format(t=nums, v=__version__), encoding="utf-8")
    print("assets ->", OUT, "version", __version__)


if __name__ == "__main__":
    main()
