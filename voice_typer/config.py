"""User settings, saved as JSON in %APPDATA%\\VoiceTyper\\settings.json."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_DIR = Path(os.environ.get("APPDATA", Path.home())) / "VoiceTyper"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
HISTORY_FILE = SETTINGS_DIR / "history.json"


@dataclass
class Config:
    # Model & recognition
    model: str = "small"            # catalog name, HF repo id ("repo#subfolder" allowed) or local folder
    language: str | None = None     # None = auto-detect, else an ISO code like "fr"
    favorite_languages: list[str] = field(default_factory=lambda: ["fr", "en"])
    device: str = "auto"            # "auto" (GPU if available) | "cuda" | "cpu"
    compute_type: str = "int8"      # used on CPU
    gpu_compute_type: str = "float16"  # used on an NVIDIA GPU
    # Dictionary
    vocabulary: list[str] = field(default_factory=list)       # terms to bias recognition towards
    replacements: list[dict] = field(default_factory=list)    # [{"from": "...", "to": "..."}]
    # Shortcuts
    hotkey: str = "ctrl+alt+space"
    mode: str = "hold"              # "hold" (push-to-talk) | "toggle" (press to start, press to stop)
    language_hotkey: str = ""       # cycles through favorite languages ("" = off)
    # Audio
    input_device: str | None = None  # microphone name, None = Windows default
    sounds: bool = True             # short beep on start / stop
    # Output
    output: str = "paste"           # "paste" | "type"
    trailing_space: bool = True
    # Interface
    overlay: bool = True            # floating indicator while dictating
    ui_language: str = "fr"         # "fr" | "en"
    theme: str = "system"           # "system" | "light" | "dark"
    history_enabled: bool = True
    custom_models: list[dict] = field(default_factory=list)  # [{"label": ..., "source": ...}]
    sample_rate: int = 16_000
    settings_version: int = 2

    @classmethod
    def load(cls) -> "Config":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if known.get("settings_version", 1) < 2:
            # v1 always saved device="cpu" (it was the only option): switch to auto-detect.
            if known.get("device") == "cpu":
                known["device"] = "auto"
            known["settings_version"] = 2
        return cls(**known)

    def save(self) -> None:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SETTINGS_FILE)


def load_history() -> list[dict]:
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_history(items: list[dict]) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(items[-200:], indent=2, ensure_ascii=False), encoding="utf-8")
