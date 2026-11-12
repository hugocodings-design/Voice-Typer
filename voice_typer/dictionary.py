"""Personal dictionary: terms that bias recognition + automatic text replacements."""

import re


def for_app(vocabulary: list[str], replacements: list[dict], app_dictionaries: list[dict] | None,
            exe: str) -> tuple[list[str], list[dict]]:
    """The words and replacements for a dictation in `exe` ("outlook.exe"): the general dictionary
    plus that application's own entries. An app replacement replaces the general one for the same words."""
    rule = next((d for d in app_dictionaries or [] if exe and d.get("app", "").lower() == exe.lower()), None)
    if not rule:
        return list(vocabulary), list(replacements)
    vocab = list(vocabulary)
    seen = {v.lower() for v in vocab}
    vocab += [v for v in rule.get("vocabulary", []) if v.lower() not in seen]
    own = list(rule.get("replacements", []))
    overridden = {(r.get("from") or "").strip().lower() for r in own}
    return vocab, own + [r for r in replacements if (r.get("from") or "").strip().lower() not in overridden]


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
