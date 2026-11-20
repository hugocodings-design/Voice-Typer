"""Export / import of the user's settings, to set up Voice Typer on another PC in one step.

Only what is the user's own work and taste travels (dictionary, per-app dictionaries, AI presets,
shortcuts, output and interface choices). What belongs to one machine stays: microphone,
update state, history, local model folders. It is a plain file: nothing goes over the network.
"""

import json
from dataclasses import fields
from pathlib import Path

from voice_typer import __version__, models
from voice_typer.config import Config

FORMAT = "voice-typer-settings"
FORMAT_VERSION = 1
MAX_FILE_SIZE = 5 * 1024 * 1024

PORTABLE = (
    # recognition
    "model", "language", "device", "compute_type", "gpu_compute_type", "custom_models",
    # dictionary
    "vocabulary", "replacements", "app_dictionaries",
    # AI writing
    "writing_model", "presets", "signature", "signature_en", "signature_blank_line", "writer_preload", "rewrite_preset", "app_presets",
    # shortcuts
    "hotkey", "mode", "language_hotkey", "paste_last_hotkey", "undo_hotkey", "rewrite_hotkey",
    # output
    "output", "trailing_space", "keep_in_clipboard", "voice_commands", "live_preview", "live_typing",
    "sounds", "remove_fillers", "numbers_as_digits", "speed_mode", "all_cores",
    # interface
    "overlay", "mic_button", "close_action", "ui_language", "theme", "history_enabled", "auto_update",
)

# Each field's accepted JSON type(s), from the Config defaults (None allowed where the default is None).
_TYPES = {
    "language": (str, type(None)),
    "presets": (list, type(None)),
    "mic_button_pos": (list, type(None)),
}


class ImportError_(ValueError):
    """The file is not a Voice Typer settings export (message: an i18n key)."""


def _portable_model(source) -> bool:
    # a local folder only exists on one PC; catalog names and Hugging Face ids ("org/name") work everywhere
    if not isinstance(source, str) or not source.strip():
        return False
    looks_like_path = ":" in source or "\\" in source or source.startswith(("/", ".", "~"))
    return not looks_like_path and not models.is_local_folder(source)


def export_settings(cfg: Config, path) -> dict:
    data = {}
    for name in PORTABLE:
        value = getattr(cfg, name)
        if name == "model" and not _portable_model(value):
            continue
        if name == "custom_models":
            value = [m for m in value if isinstance(m, dict) and _portable_model(m.get("source"))]
        data[name] = value
    doc = {"format": FORMAT, "format_version": FORMAT_VERSION, "app_version": __version__, "settings": data}
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return doc


def _expected_type(name: str):
    if name in _TYPES:
        return _TYPES[name]
    default = {f.name: f for f in fields(Config)}[name]
    value = default.default_factory() if callable(default.default_factory) else default.default
    if isinstance(value, bool):
        return (bool,)
    return (type(value),)


def _valid(name: str, value) -> bool:
    expected = _expected_type(name)
    if bool not in expected and isinstance(value, bool):
        return False  # JSON true/false is not an acceptable int / str
    if not isinstance(value, expected):
        return False
    if name in ("replacements",):
        return all(isinstance(r, dict) and isinstance(r.get("from"), str) and isinstance(r.get("to"), str)
                   for r in value)
    if name == "vocabulary":
        return all(isinstance(w, str) for w in value)
    if name in ("app_dictionaries", "app_presets", "custom_models"):
        return all(isinstance(d, dict) for d in value)
    if name == "presets" and value is not None:
        return all(isinstance(p, dict) and isinstance(p.get("id"), str) for p in value)
    if name == "model":
        return _portable_model(value)
    return True


def read_export(path) -> dict:
    """Validated settings from an export file. Raises ImportError_ with an i18n key."""
    p = Path(path)
    try:
        if p.stat().st_size > MAX_FILE_SIZE:
            raise ImportError_("xfer_bad_file")
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ImportError_("xfer_bad_file") from exc
    if not isinstance(doc, dict) or doc.get("format") != FORMAT or not isinstance(doc.get("settings"), dict):
        raise ImportError_("xfer_bad_file")
    if not isinstance(doc.get("format_version"), int) or doc["format_version"] > FORMAT_VERSION:
        raise ImportError_("xfer_too_new")
    return {k: v for k, v in doc["settings"].items() if k in PORTABLE and _valid(k, v)}


def _merged(cfg: Config, name: str, value):
    if name == "custom_models":
        # keep the models imported from this PC's own folders (they are never exported)
        sources = {m.get("source") for m in value}
        local = [m for m in cfg.custom_models
                 if isinstance(m, dict) and not _portable_model(m.get("source")) and m.get("source") not in sources]
        return value + local
    return value


def changes(cfg: Config, settings: dict) -> list[str]:
    """Names of the settings an import would change."""
    return [name for name, value in settings.items() if getattr(cfg, name) != _merged(cfg, name, value)]


def apply_settings(cfg: Config, settings: dict) -> list[str]:
    """Copies the imported values into cfg (not saved). Returns the names that changed."""
    changed = []
    for name, value in settings.items():
        value = _merged(cfg, name, value)
        if getattr(cfg, name) != value:
            setattr(cfg, name, value)
            changed.append(name)
    if cfg.language not in (None, "fr", "en"):
        cfg.language = None
    if cfg.ui_language not in ("fr", "en"):
        cfg.ui_language = "fr"
    cfg.ensure_presets()
    return changed
