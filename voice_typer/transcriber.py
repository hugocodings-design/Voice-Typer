"""Local speech-to-text with faster-whisper."""

import numpy as np
from faster_whisper import WhisperModel

from voice_typer.config import Config


class Transcriber:
    def __init__(self, config: Config):
        self.language = config.language
        # Loaded once; first run downloads the model, afterwards it works offline.
        self.model = WhisperModel(config.model, device=config.device, compute_type=config.compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
