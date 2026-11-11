"""Local speech-to-text with faster-whisper (NVIDIA GPU when available, else CPU)."""

import numpy as np

from voice_typer import gpu

gpu.setup_dll_paths()  # must run before CTranslate2 needs cuBLAS

from faster_whisper import WhisperModel  # noqa: E402


class Transcriber:
    def __init__(self, source: str, path: str, device: str = "auto",
                 cpu_compute: str = "int8", gpu_compute: str = "float16"):
        self.source = source  # catalog id shown in the UI
        self.gpu_error: str | None = None
        want_gpu = device == "cuda" or (device == "auto" and gpu.cuda_available())
        if want_gpu:
            try:
                self.model = WhisperModel(path, device="cuda", compute_type=gpu_compute)
                # cuBLAS is only loaded on first use: run a tiny warm-up so a missing DLL fails here.
                list(self.model.transcribe(np.zeros(16000, dtype=np.float32))[0])
                self.device = "cuda"
                return
            except Exception as exc:  # noqa: BLE001 — fall back to CPU
                if "Unable to open" in str(exc):  # file still locked: retried by the caller, not a GPU problem
                    raise
                self.gpu_error = str(exc)
        self.model = WhisperModel(path, device="cpu", compute_type=cpu_compute)
        self.device = "cpu"

    def transcribe(self, audio: np.ndarray, language: str | None = None,
                   hotwords: str | None = None) -> str:
        if audio.size == 0:
            return ""
        segments, _info = self.model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            hotwords=hotwords,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def preview(self, audio: np.ndarray, language: str | None = None) -> str:
        """Fast, lower-quality pass for the live preview (greedy, no VAD). The final text is redone."""
        if audio.size < 8000:  # < 0.5 s
            return ""
        segments, _info = self.model.transcribe(
            audio, language=language, beam_size=1, vad_filter=False,
            condition_on_previous_text=False, without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
