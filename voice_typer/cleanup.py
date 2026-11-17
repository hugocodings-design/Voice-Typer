"""Transcript clean-up shared with Voice Typer Mobile (core/Text.kt).

- `strip_hallucinations`: captions Whisper invents on silence or noise ("Sous-titrage Société Radio-Canada").
- `remove_fillers`: hesitations ("euh", "um") and accidental repeated words ("le le"), without the AI.
"""

import re

_L = r"[^\W\d_]"  # a letter (any alphabet)

_HALLUCINATIONS = [
    re.compile(r"\[\s*(blank_audio|musique|music|applaudissements|rires|silence)\s*\]", re.I),
    re.compile(r"\(\s*(musique|music|applaudissements|rires|silence)\s*\)", re.I),
    re.compile(r"sous-titr(age|es|é)[^.\n]*(radio-canada|amara\.org|st' ?\d+|par la communauté)[^.\n]*\.?", re.I),
    re.compile(r"merci d'avoir regardé( cette vidéo)?[ !.]*", re.I),
    re.compile(r"(thanks|thank you) for watching[ !.]*", re.I),
    re.compile(r"abonnez-vous[^.\n]*\.?", re.I),
]


def strip_hallucinations(text: str) -> str:
    for pattern in _HALLUCINATIONS:
        text = pattern.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


_FILLERS = {
    "fr": ("ben euh", "euhm", "euh", "heu", "hum", "hmm", "bah"),
    "en": ("uhm", "uh", "um", "erm", "hmm"),
}
# "nous nous voyons", "vous vous trompez" are correct French: never collapsed
_KEEP_REPEATED = {"nous", "vous"}


def remove_fillers(text: str, language: str | None) -> str:
    """language None (auto) removes both French and English hesitations."""
    started_upper = text[:1].isupper()
    words = _FILLERS.get(language) or tuple(w for ws in _FILLERS.values() for w in ws)
    alt = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
    text = re.sub(rf"(?<!{_L})(?:{alt})(?!{_L})[,.]?\s*", "", text, flags=re.I)

    def _dedupe(m: re.Match) -> str:
        return m.group(0) if m.group(1).lower() in _KEEP_REPEATED else m.group(1)

    text = re.sub(rf"(?<!{_L})({_L}+)(?:\s+\1)+(?!{_L})", _dedupe, text, flags=re.I)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    # the removed filler carried the sentence's capital letter: "Euh, je pense" → "Je pense"
    if started_upper and text[:1].islower():
        text = text[0].upper() + text[1:]
    return text
