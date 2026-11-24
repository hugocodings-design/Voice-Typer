"""Speed choices (Réglages → Vitesse) and the time breakdown shown after each dictation.

- Transcription mode: "accurate" = beam search with 5 candidates (best on an NVIDIA card); "fast" = a single
  candidate, no timestamps, no context carried between windows — 2 to 3× faster on a processor, nearly the
  same text for short dictations; "auto" = fast on CPU, accurate on GPU.
- All cores: CTranslate2 uses 4 threads by default (intra_threads=0); on a 6–16 core PC more threads make both
  Whisper and the writing AI faster. Hyper-threads add little, so we count about one thread per physical core.
"""

import os

MODES = ("auto", "fast", "accurate")


def cpu_threads(all_cores: bool, logical: int | None = None) -> int:
    """Threads for CTranslate2 on the CPU. 0 = its own default (4)."""
    if not all_cores:
        return 0
    logical = logical or os.cpu_count() or 4
    physical = logical // 2 if logical >= 8 else logical  # hyper-threading usually doubles the count
    return max(4, physical)


def effective_mode(mode: str, device: str) -> str:
    if mode not in MODES or mode == "auto":
        return "accurate" if device == "cuda" else "fast"
    return mode


def decode_options(mode: str, device: str) -> dict:
    """faster-whisper `transcribe()` options for the chosen mode."""
    if effective_mode(mode, device) == "fast":
        return {"beam_size": 1, "best_of": 1, "without_timestamps": True, "condition_on_previous_text": False}
    return {"beam_size": 5}


def format_timings(t: dict, lang: str = "fr") -> str:
    """'audio 4.2 s · transcription 1.1 s · IA 2.3 s · objet 0.4 s' — only the steps that ran."""
    labels = {"fr": {"audio": "audio", "transcribe": "transcription", "rewrite": "IA", "subject": "objet",
                     "paste": "écriture"},
              "en": {"audio": "audio", "transcribe": "transcription", "rewrite": "AI", "subject": "subject",
                     "paste": "typing"}}.get(lang, {})
    if not labels:
        labels = {k: k for k in ("audio", "transcribe", "rewrite", "subject", "paste")}
    dec = "," if lang == "fr" else "."
    parts = []
    for key in ("audio", "transcribe", "rewrite", "subject", "paste"):
        value = t.get(key)
        if value is None or (key != "audio" and value < 0.05):
            continue
        def s(v):
            return f"{v:.1f}".replace(".", dec) + " s"

        part = f"{labels[key]} {s(value)}"
        home_word, net_word = ("maison", "réseau") if lang == "fr" else ("home", "network")
        if key == "transcribe" and t.get("home"):
            compute = t.get("home_compute")
            if isinstance(compute, (int, float)) and value >= compute:
                # where the time goes: on the home PC's graphics card, or on the way (internet, Funnel)
                part += f" ({home_word} : {s(compute)} + {net_word} {s(value - compute)})" if lang == "fr" else \
                    f" ({home_word}: {s(compute)} + {net_word} {s(value - compute)})"
            else:
                part += f" ({home_word})"
        elif key in ("rewrite", "subject") and t.get("home_ai"):
            net = t.get("home_ai_net")
            last_ai = "subject" if t.get("subject", 0) >= 0.05 else "rewrite"
            if key == last_ai and isinstance(net, (int, float)) and net >= 0.05:
                part += f" ({home_word}, + {net_word} {s(net)})"
            else:
                part += f" ({home_word})"
        parts.append(part)
    return " · ".join(parts)
