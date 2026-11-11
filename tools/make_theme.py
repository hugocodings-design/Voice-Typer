"""Generates voice_typer/theme/: the Sun Valley ttk theme (sv-ttk, MIT) recoloured green and gray.

Run once after changing the colours below, then commit voice_typer/theme/:
    venv\\Scripts\\python.exe tools\\make_theme.py
"""

import colorsys
import re
import shutil
from pathlib import Path

import sv_ttk
from PIL import Image

SRC = Path(sv_ttk.__file__).parent
DST = Path(__file__).resolve().parents[1] / "voice_typer" / "theme"

# Original accent of each sprite sheet -> our green. Every blue-ish pixel keeps its offset in
# lightness / saturation from the original accent, so hover / pressed / disabled states stay coherent.
ACCENTS = {
    "light": {"from": (0, 95, 184), "to": (34, 197, 94)},     # #22c55e
    "dark": {"from": (87, 200, 255), "to": (74, 222, 128)},   # #4ade80
}

# Tcl colour edits: (file, old, new)
TCL_EDITS = {
    "light.tcl": [
        ('-fg      "#1c1c1c"', '-fg      "#1a1d1b"'),
        ('-selbg   "#2f60d8"', '-selbg   "#16a34a"'),
        ('-accent  "#005fb8"', '-accent  "#22c55e"'),
        # dark text on the bright green buttons (white on bright green is hard to read)
        ('Accent.TButton -padding {8 2 8 3} -anchor center -foreground "#ffffff"',
         'Accent.TButton -padding {8 2 8 3} -anchor center -foreground "#052e16"'),
        ('Accent.TButton -foreground [list pressed "#c1d8ee" disabled "#ffffff"]',
         'Accent.TButton -foreground [list pressed "#14532d" disabled "#ffffff"]'),
        ('{selected pressed} "#636363" \\\n        selected "#ffffff" \\\n        pressed "#c1d8ee"',
         '{selected pressed} "#14532d" \\\n        selected "#052e16" \\\n        pressed "#14532d"'),
        ('Treeview -background {selected "#e7e7e7"} -foreground {selected "#191919"}',
         'Treeview -background {selected "#dcfce7"} -foreground {selected "#14532d"}'),
    ],
    "dark.tcl": [
        ('-selbg   "#2f60d8"', '-selbg   "#15803d"'),
        ('-accent  "#57c8ff"', '-accent  "#4ade80"'),
        ('pressed "#25536a"', 'pressed "#14532d"'),
        ('Treeview -background {selected "#292929"}', 'Treeview -background {selected "#1f3a29"}'),
    ],
}


def recolor(src: Path, dst: Path, base: tuple, target: tuple) -> int:
    im = Image.open(src).convert("RGBA")
    bh, bl, bs = colorsys.rgb_to_hls(*(c / 255 for c in base))
    th, tl, ts = colorsys.rgb_to_hls(*(c / 255 for c in target))
    px = im.load()
    changed = 0
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if s < 0.25 or not 0.45 < h < 0.75:  # not part of the blue accent
                continue
            nl = min(max(tl + (l - bl), 0), 1)
            ns = min(max(ts * (s / bs if bs else 1), 0), 1)
            nr, ng, nb = colorsys.hls_to_rgb(th, nl, ns)
            px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
            changed += 1
    im.save(dst)
    return changed


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    (DST / "theme").mkdir(parents=True)
    shutil.copy(SRC / "sv.tcl", DST / "sv.tcl")
    for f in (SRC / "theme").glob("sprites_*.tcl"):
        shutil.copy(f, DST / "theme" / f.name)
    for name, edits in TCL_EDITS.items():
        text = (SRC / "theme" / name).read_text(encoding="utf-8")
        for old, new in edits:
            if old not in text:
                raise SystemExit(f"{name}: pattern not found (sv-ttk changed?): {old[:60]}")
            text = text.replace(old, new)
        if re.search(r"#(005fb8|57c8ff|2f60d8)", text):
            raise SystemExit(f"{name}: a blue colour is left")
        (DST / "theme" / name).write_text(text, encoding="utf-8")
    for mode, acc in ACCENTS.items():
        n = recolor(SRC / "theme" / f"spritesheet_{mode}.png", DST / "theme" / f"spritesheet_{mode}.png",
                    acc["from"], acc["to"])
        print(f"{mode}: {n} pixels recoloured")
    lic = next(SRC.parent.glob("sv_ttk-*.dist-info/licenses/LICENSE"), None)
    note = "Sun Valley ttk theme by rdbende (sv-ttk), recoloured for Voice Typer by tools/make_theme.py.\n\n"
    (DST / "LICENSE.txt").write_text(note + (lic.read_text(encoding="utf-8") if lic else "MIT License"),
                                     encoding="utf-8")
    print("theme ->", DST)


if __name__ == "__main__":
    main()
