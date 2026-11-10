"""Catalog of Whisper models + helpers to check, download and import them."""

from dataclasses import dataclass
from pathlib import Path

from faster_whisper.utils import download_model


@dataclass(frozen=True)
class ModelInfo:
    source: str        # what WhisperModel() receives: catalog name, HF repo id or folder path
    label: str
    size: str = ""
    speed: str = ""    # rough, on a typical CPU
    accuracy: str = ""
    note: str = ""
    custom: bool = False


CATALOG: list[ModelInfo] = [
    ModelInfo("tiny", "Tiny", "75 MB", "★★★★★", "★☆☆☆☆", "Instant, but many mistakes"),
    ModelInfo("base", "Base", "145 MB", "★★★★☆", "★★☆☆☆", "Fast, OK for short sentences"),
    ModelInfo("small", "Small", "480 MB", "★★★☆☆", "★★★☆☆", "Good balance (default)"),
    ModelInfo("medium", "Medium", "1.5 GB", "★★☆☆☆", "★★★★☆", "Accurate, slower on CPU"),
    ModelInfo("large-v3-turbo", "Large v3 Turbo", "1.6 GB", "★★☆☆☆", "★★★★★",
              "Near-best accuracy, much faster than Large v3"),
    ModelInfo("large-v3", "Large v3", "3.1 GB", "★☆☆☆☆", "★★★★★", "Best accuracy, slow without a GPU"),
    ModelInfo("distil-large-v3.5", "Distil Large v3.5", "1.5 GB", "★★★☆☆", "★★★★☆",
              "English only"),
]

# Most-used languages first; Whisper supports ~100 in total.
LANGUAGES: list[tuple[str | None, str]] = [
    (None, "Auto-detect"),
    ("fr", "Français"),
    ("en", "English"),
    ("es", "Español"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("nl", "Nederlands"),
    ("ar", "العربية (Arabic)"),
    ("zh", "中文 (Chinese)"),
    ("ja", "日本語 (Japanese)"),
    ("ko", "한국어 (Korean)"),
    ("ru", "Русский (Russian)"),
    ("pl", "Polski"),
    ("tr", "Türkçe"),
    ("hi", "हिन्दी (Hindi)"),
    ("uk", "Українська (Ukrainian)"),
    ("sv", "Svenska"),
    ("vi", "Tiếng Việt"),
    ("he", "עברית (Hebrew)"),
]


def all_models(custom: list[dict]) -> list[ModelInfo]:
    extra = [
        ModelInfo(c["source"], c["label"], note="Imported model", custom=True) for c in custom
    ]
    return CATALOG + extra


def is_local_folder(source: str) -> bool:
    return Path(source).is_dir()


def is_downloaded(source: str) -> bool:
    if is_local_folder(source):
        return (Path(source) / "model.bin").exists()
    try:
        download_model(source, local_files_only=True)
        return True
    except Exception:  # noqa: BLE001 — any failure means "not available offline"
        return False


def download(source: str) -> str:
    """Download a catalog model or Hugging Face repo (CTranslate2 format). Returns its local path."""
    if is_local_folder(source):
        return source
    return download_model(source)


def validate_folder(folder: str) -> str | None:
    """Return an error message if the folder isn't a faster-whisper (CTranslate2) model, else None."""
    p = Path(folder)
    missing = [f for f in ("model.bin", "config.json") if not (p / f).exists()]
    if missing:
        return (
            f"This folder is missing {', '.join(missing)}.\n\n"
            "Voice Typer needs a Whisper model converted to CTranslate2 format "
            "(the kind published as 'faster-whisper-…' on Hugging Face)."
        )
    return None
