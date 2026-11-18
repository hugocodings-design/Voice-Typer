"""Portable package: dist/VoiceTyper-portable-<version>.zip, run by build.ps1 after the self-test.

The zip holds the PyInstaller folder build (dist/Voice Typer) at its root plus `portable.txt`, so that
"Extract all" to C:\\Dev\\VoiceTyper\\ gives C:\\Dev\\VoiceTyper\\Voice Typer.exe. No installer, no unpacking at
startup, no use of %TEMP% (see voice_typer/portable.py).

    venv\\Scripts\\python.exe installer\\make_portable.py --src "dist\\Voice Typer" --version 0.12.0 --out dist
"""

import argparse
import zipfile
from pathlib import Path

README = """Voice Typer — version portable

Extrayez TOUT le contenu de ce zip dans un dossier, par exemple C:\\Dev\\VoiceTyper\\, puis lancez
« Voice Typer.exe ». Aucune installation, aucun droit d'administrateur, et le dossier temporaire de Windows
(%TEMP%) n'est jamais utilisé : Voice Typer utilise son propre dossier « tmp » à côté de l'exécutable.

Ce fichier indique à Voice Typer qu'il est en mode portable : ne le supprimez pas. Les mises à jour se font
dans ce même dossier. Les réglages restent dans %APPDATA%\\VoiceTyper et les modèles d'IA dans
%USERPROFILE%\\.cache\\huggingface.
"""


def build(src: Path, version: str, out: Path) -> Path:
    if not (src / "Voice Typer.exe").is_file():
        raise SystemExit(f"{src} ne contient pas Voice Typer.exe : lancez d'abord PyInstaller.")
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"VoiceTyper-portable-{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(src).as_posix())
        z.writestr("portable.txt", README)
    return zip_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    path = build(a.src, a.version, a.out)
    print(f"Version portable : {path} ({round(path.stat().st_size / 1e6)} Mo)")


if __name__ == "__main__":
    main()
