"""Personal dictionary: terms that bias recognition + automatic text replacements."""

import re


def hotwords(vocabulary: list[str]) -> str | None:
    """Terms passed to Whisper as hints (faster-whisper `hotwords`)."""
    terms = [t.strip() for t in vocabulary if t.strip()]
    return ", ".join(terms) if terms else None


def apply_replacements(text: str, replacements: list[dict]) -> str:
    """Replace whole words/phrases, ignoring case: e.g. "chat GPT" → "ChatGPT"."""
    for rule in replacements:
        src = (rule.get("from") or "").strip()
        if not src:
            continue
        dst = rule.get("to") or ""
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in src.split()) + r"(?!\w)"
        text = re.sub(pattern, lambda _m: dst, text, flags=re.IGNORECASE)
    return text
