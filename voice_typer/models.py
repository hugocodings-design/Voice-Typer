"""Catalog of Whisper models + helpers to check, download and import them.

A model "source" can be:
- a faster-whisper catalog name ("small", "large-v3-turbo", "distil-small.en"…)
- a Hugging Face repo id holding a CTranslate2 model ("Systran/faster-whisper-large-v3")
- a repo id + subfolder, written "owner/repo#subfolder" (e.g. bofenghuang's French models,
  which keep their CTranslate2 files in a "ctranslate2/" folder)
- a local folder path
"""

from dataclasses import dataclass
from pathlib import Path

from faster_whisper.utils import download_model
from huggingface_hub import HfApi, snapshot_download


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
    # The "distil" versions keep the full encoder but only 2 or 16 decoder layers → much faster.
    ModelInfo("bofenghuang/whisper-large-v3-french-distil-dec2#ctranslate2", "Français Distil (rapide)",
              "fr", "1.5 GB", "★★★☆☆", "★★★★☆"),
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

# Most-used languages first; Whisper supports ~100 in total.
LANGUAGES: list[tuple[str | None, str]] = [
    (None, "Auto"),  # label replaced by the UI language
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
    extra = [ModelInfo(c["source"], c["label"], "custom", custom=True) for c in custom]
    return CATALOG + extra


def is_local_folder(source: str) -> bool:
    return Path(source).is_dir()


def resolve(source: str, local_only: bool = False) -> str:
    """Return the local folder of a model, downloading it first unless local_only."""
    if is_local_folder(source):
        return source
    if "#" in source:
        repo, sub = source.split("#", 1)
        root = snapshot_download(repo, allow_patterns=[f"{sub}/*"], local_files_only=local_only)
        path = Path(root) / sub
        if not (path / "model.bin").exists():
            raise FileNotFoundError(f"{source}: model.bin not found")
        return str(path)
    return download_model(source, local_files_only=local_only)


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


def missing_model_files(folder: str) -> str | None:
    """Return the missing files if the folder isn't a faster-whisper (CTranslate2) model, else None."""
    p = Path(folder)
    missing = [f for f in ("model.bin", "config.json") if not (p / f).exists()]
    return ", ".join(missing) if missing else None
