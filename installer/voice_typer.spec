# PyInstaller recipe: turns run.pyw + the venv into a standalone folder (dist/Voice Typer).
# Run through build.ps1, not by hand.
import site
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
ASSETS = Path(SPECPATH) / "build_assets"

datas, binaries, hiddenimports = [], [], collect_submodules("voice_typer")
for pkg in ("ctranslate2", "faster_whisper", "tokenizers", "onnxruntime", "sv_ttk",
            "sounddevice", "_sounddevice_data", "av", "huggingface_hub", "pystray"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:  # package missing: skip
        continue
    datas += d
    binaries += b
    hiddenimports += h

# NVIDIA cuBLAS / NVRTC DLLs (GPU acceleration). gpu.setup_dll_paths() finds them under
# <app>/_internal/nvidia/*/bin. nvblas is a BLAS shim nothing here uses.
for sp in site.getsitepackages():
    for dll in Path(sp, "nvidia").glob("*/bin/*.dll"):
        if not dll.name.startswith("nvblas"):
            binaries.append((str(dll), f"nvidia/{dll.parent.parent.name}/bin"))

a = Analysis(
    [str(ROOT / "run.pyw")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["pystray._win32", "PIL.ImageTk"],
    excludes=["pytest", "pyflakes", "matplotlib", "IPython", "notebook", "torch"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Voice Typer",
    icon=str(ASSETS / "app.ico"),
    console=False,
    upx=False,
    version=str(ASSETS / "version_info.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Voice Typer")
