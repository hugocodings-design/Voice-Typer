"""User settings, saved as JSON in %APPDATA%\\VoiceTyper\\settings.json."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_DIR = Path(os.environ.get("APPDATA", Path.home())) / "VoiceTyper"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class Config:
    model: str = "small"            # catalog name, Hugging Face repo id, or local folder path
    language: str | None = None     # None = auto-detect, else an ISO code like "fr"
    device: str = "cpu"             # "cpu" or "cuda"
    compute_type: str = "int8"
    hotkey: str = "ctrl+alt+space"
    mode: str = "hold"              # "hold" (push-to-talk) | "toggle" (press to start, press to stop)
    output: str = "paste"           # "paste" | "type"
    overlay: bool = True            # floating indicator while dictating
    ui_language: str = "fr"         # "fr" | "en"
    custom_models: list[dict] = field(default_factory=list)  # [{"label": ..., "source": ...}]
    sample_rate: int = 16_000

    @classmethod
    def load(cls) -> "Config":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
