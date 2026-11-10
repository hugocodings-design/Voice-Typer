"""Local speech-to-text with faster-whisper."""

import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, source: str, path: str, device: str = "cpu", compute_type: str = "int8"):
        self.source = source  # catalog id shown in the UI
        self.model = WhisperModel(path, device=device, compute_type=compute_type)

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> str:
        if audio.size == 0:
            return ""
        segments, _info = self.model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
