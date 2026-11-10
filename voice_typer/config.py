"""Settings, overridable with VT_* environment variables."""

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None) -> str | None:
    value = os.environ.get(name)
    return value if value else default


@dataclass(frozen=True)
class Config:
    model: str = field(default_factory=lambda: _env("VT_MODEL", "small"))
    language: str | None = field(default_factory=lambda: _env("VT_LANGUAGE", None))
    device: str = field(default_factory=lambda: _env("VT_DEVICE", "cpu"))
    compute_type: str = field(default_factory=lambda: _env("VT_COMPUTE_TYPE", "int8"))
    hotkey: str = field(default_factory=lambda: _env("VT_HOTKEY", "ctrl+alt+space"))
    output: str = field(default_factory=lambda: _env("VT_OUTPUT", "paste"))  # "paste" | "type"
    sample_rate: int = 16_000
