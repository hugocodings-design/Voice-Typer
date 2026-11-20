"""Catalog of Whisper models + helpers to check, download and import them.

A model "source" can be:
- a faster-whisper catalog name ("small", "large-v3-turbo", "distil-small.en"…)
- a Hugging Face repo id holding a CTranslate2 model ("Systran/faster-whisper-large-v3")
- a repo id + subfolder, written "owner/repo#subfolder" (e.g. bofenghuang's French models,
  which keep their CTranslate2 files in a "ctranslate2/" folder)
- a local folder path
"""

import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from faster_whisper.utils import download_model  # noqa: E402
from huggingface_hub import HfApi, snapshot_download  # noqa: E402


def retry_while_locked(load, attempts: int = 20, delay: float = 3.0):
    """Call `load()`, retrying while the model file can't be opened yet.

    Right after a download, Windows (usually the antivirus scanning the new, very large file)
    can hold model.bin for a few seconds (also on the first start after an update, when the new
    executable is scanned): CTranslate2 then fails with "Unable to open file". Retries for ~1 min.
    """
    import time

    for attempt in range(attempts):
        try:
            return load()
        except Exception as exc:  # noqa: BLE001
            if "Unable to open" not in str(exc) or attempt == attempts - 1:
                raise
            time.sleep(delay)


@dataclass(frozen=True)
class ModelInfo:
    source: str
    label: str
    group: str = "custom"  # "multi" | "fr" | "en" | "custom"
    size: str = ""
    speed: str = ""        # rough, on a typical CPU
    accuracy: str = ""
    note: str = ""
    custom: bool = False


GROUPS = ["fr", "multi", "en", "custom"]

CATALOG: list[ModelInfo] = [
    # French-specialised: Whisper Large v3 fine-tuned on ~2,500 h of French (bofenghuang, MIT license).
    # The "distil" versions keep the full encoder but only 2, 4 or 16 decoder layers → much faster.
    ModelInfo("bofenghuang/whisper-large-v3-french-distil-dec2#ctranslate2", "Français Distil (rapide)",
              "fr", "1.5 GB", "★★★☆☆", "★★★★☆"),
    ModelInfo("bofenghuang/whisper-large-v3-french-distil-dec4#ctranslate2", "Français Distil (équilibré)",
              "fr", "1.6 GB", "★★★☆☆", "★★★★½"),
    ModelInfo("bofenghuang/whisper-large-v3-french-distil-dec16#ctranslate2", "Français Distil (précis)",
              "fr", "2.2 GB", "★★☆☆☆", "★★★★★"),
    ModelInfo("bofenghuang/whisper-large-v3-french#ctranslate2", "Français Large v3",
              "fr", "3.1 GB", "★☆☆☆☆", "★★★★★"),
    # Multilingual (French, English and ~100 other languages)
    ModelInfo("tiny", "Tiny", "multi", "75 MB", "★★★★★", "★☆☆☆☆"),
    ModelInfo("base", "Base", "multi", "145 MB", "★★★★☆", "★★☆☆☆"),
    ModelInfo("small", "Small", "multi", "480 MB", "★★★☆☆", "★★★☆☆"),
    ModelInfo("medium", "Medium", "multi", "1.5 GB", "★★☆☆☆", "★★★★☆"),
    ModelInfo("Zoont/faster-whisper-large-v3-turbo-int8-ct2", "Large v3 Turbo (compact)",
              "multi", "810 MB", "★★☆☆☆", "★★★★★"),
    ModelInfo("large-v3-turbo", "Large v3 Turbo", "multi", "1.6 GB", "★★☆☆☆", "★★★★★"),
    ModelInfo("large-v3", "Large v3", "multi", "3.1 GB", "★☆☆☆☆", "★★★★★"),
    # English-only distilled models: faster than multilingual models of similar accuracy
    ModelInfo("distil-small.en", "English Distil Small", "en", "330 MB", "★★★★☆", "★★★☆☆"),
    ModelInfo("distil-medium.en", "English Distil Medium", "en", "790 MB", "★★★☆☆", "★★★★☆"),
    ModelInfo("distil-large-v3.5", "English Distil Large v3.5", "en", "1.5 GB", "★★★☆☆", "★★★★★"),
]

def all_models(custom: list[dict]) -> list[ModelInfo]:
    extra = [ModelInfo(c["source"], c["label"], "custom", custom=True) for c in custom]
    return CATALOG + extra


def is_local_folder(source: str) -> bool:
    return Path(source).is_dir()


def unlink_symlinks(folder) -> str:
    """Replace symbolic links in a model folder by hard links (or copies) of their target.

    huggingface_hub 2.x ("shared blobs" cache) turns model files into symlinks to
    hub/blobs/xx/…; CTranslate2 inside the packaged app then fails with "Unable to open file
    'model.bin'" (works from source). Same disk → hard link, so no extra space is used."""
    import os
    import shutil

    for f in Path(folder).iterdir():
        try:
            if not f.is_symlink():
                continue
            target = f.resolve(strict=True)
            tmp = f.with_name(f.name + ".vt-tmp")
            if tmp.exists():
                tmp.unlink()
            try:
                os.link(target, tmp)
            except OSError:
                shutil.copy2(target, tmp)
            os.replace(tmp, f)
        except OSError:
            continue  # leave it: loading reports a clear error if it really can't be read
    return str(folder)


def resolve(source: str, local_only: bool = False) -> str:
    """Return the local folder of a model, downloading it first unless local_only.

    A model already on the PC is used as is: no request to Hugging Face (network only for a first download)."""
    if is_local_folder(source):
        return source
    if not local_only:
        try:
            return resolve(source, local_only=True)
        except Exception:  # noqa: BLE001 — not (fully) downloaded yet
            pass
    if "#" in source:
        repo, sub = source.split("#", 1)
        root = snapshot_download(repo, allow_patterns=[f"{sub}/*"], local_files_only=local_only)
        path = Path(root) / sub
        if not (path / "model.bin").exists():
            raise FileNotFoundError(f"{source}: model.bin not found")
        return unlink_symlinks(path)
    return unlink_symlinks(download_model(source, local_files_only=local_only))


def is_downloaded(source: str) -> bool:
    try:
        return (Path(resolve(source, local_only=True)) / "model.bin").exists()
    except Exception:  # noqa: BLE001 — any failure means "not available offline"
        return False


def hf_source_for(repo: str) -> str | None:
    """Find where the CTranslate2 model lives in a Hugging Face repo (root or ctranslate2/)."""
    files = set(HfApi().list_repo_files(repo))
    if "model.bin" in files and "config.json" in files:
        return repo
    for f in sorted(files):
        if f.endswith("/model.bin") and f.count("/") == 1:
            return f"{repo}#{f.split('/')[0]}"
    return None


def repo_of(source: str) -> str | None:
    """Hugging Face repo id behind a source (None for local folders)."""
    if is_local_folder(source):
        return None
    if "#" in source:
        return source.split("#", 1)[0]
    if "/" in source:
        return source
    from faster_whisper.utils import _MODELS

    return _MODELS.get(source)


def _cache_dir(source: str) -> Path | None:
    repo = repo_of(source)
    if not repo:
        return None
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE) / ("models--" + repo.replace("/", "--"))


def disk_size(source: str) -> int:
    """Bytes used on disk by a downloaded model (0 if not downloaded)."""
    folder = Path(source) if is_local_folder(source) else _cache_dir(source)
    if not folder or not folder.exists():
        return 0
    # The HF cache stores real files in blobs/ (snapshots/ only holds links).
    target = folder / "blobs" if (folder / "blobs").exists() else folder
    return sum(f.stat().st_size for f in target.rglob("*") if f.is_file())


def delete_files(source: str) -> bool:
    """Delete a downloaded model from the Hugging Face cache. Never deletes a user's own folder."""
    import shutil

    folder = _cache_dir(source)
    if folder is None or not folder.exists():
        return False
    shutil.rmtree(folder)
    return True


def human_size(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.0f} MB"
    return f"{n / 1e3:.0f} KB" if n else "0"


def missing_model_files(folder: str) -> str | None:
    """Return the missing files if the folder isn't a faster-whisper (CTranslate2) model, else None."""
    p = Path(folder)
    missing = [f for f in ("model.bin", "config.json") if not (p / f).exists()]
    return ", ".join(missing) if missing else None
