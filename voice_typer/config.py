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
    # AI writing (post-processing presets)
    writing_model: str = "jncraton/Qwen2.5-3B-Instruct-ct2-int8"
    presets: list[dict] | None = None   # [{"id","name","hotkey","instructions"}], None = defaults
    signature: str = ""
    writer_preload: bool = True         # keep the writing AI loaded (instant presets)
    # Shortcuts
    hotkey: str = "ctrl+alt+space"
    mode: str = "hold"              # "hold" (push-to-talk) | "toggle" (press to start, press to stop)
    language_hotkey: str = ""       # cycles through favorite languages ("" = off)
    paste_last_hotkey: str = ""     # types the last transcription again ("" = off)
    # Audio
    input_device: str | None = None  # microphone name, None = Windows default
    sounds: bool = True             # short beep on start / stop
    # Output
    output: str = "paste"           # "paste" | "type"
    trailing_space: bool = True
    keep_in_clipboard: bool = True  # leave the last transcription on the clipboard (Ctrl+V works again)
    voice_commands: bool = True     # "à la ligne", "virgule"… → formatting (see commands.py)
    live_preview: bool = False      # show the transcription in real time while speaking
    rewrite_hotkey: str = ""        # rewrite the selected text with a preset ("" = off)
    rewrite_preset: str = "fix"     # preset id used by rewrite_hotkey
    app_presets: list[dict] = field(default_factory=list)  # [{"app": "outlook.exe", "preset": "email"}]
    first_run_done: bool = False    # welcome assistant shown
    # Interface
    overlay: bool = True            # floating indicator while dictating
    ui_language: str = "fr"         # "fr" | "en"
    theme: str = "system"           # "system" | "light" | "dark"
    history_enabled: bool = True
    custom_models: list[dict] = field(default_factory=list)  # [{"label": ..., "source": ...}]
    sample_rate: int = 16_000
    settings_version: int = 3

    @classmethod
    def load(cls) -> "Config":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cfg = cls()
            cfg.ensure_presets()
            return cfg
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if known.get("settings_version", 1) < 2:
            # v1 always saved device="cpu" (it was the only option): switch to auto-detect.
            if known.get("device") == "cpu":
                known["device"] = "auto"
            known["settings_version"] = 2
        if "first_run_done" not in data:  # settings from before the assistant existed: not a new user
            known["first_run_done"] = True
        cfg = cls(**known)
        if known.get("settings_version", 1) < 3 and cfg.presets:
            # v2 (first AI-writing build) saved early default instructions: refresh the built-in
            # presets to the improved ones, keeping the user's names and shortcuts.
            from voice_typer.writer import default_presets

            defaults = {p["id"]: p for p in default_presets(cfg.ui_language)}
            for p in cfg.presets:
                if p.get("id") in defaults:
                    p["instructions"] = defaults[p["id"]]["instructions"]
        cfg.settings_version = 3
        cfg.ensure_presets()
        return cfg

    def ensure_presets(self) -> None:
        if self.presets is None:
            from voice_typer.writer import default_presets

            self.presets = default_presets(self.ui_language)
            # Don't steal a key the user already uses for dictation / language switching.
            taken = {self.hotkey, self.language_hotkey}
            for p in self.presets:
                if p["hotkey"] in taken:
                    p["hotkey"] = ""

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
