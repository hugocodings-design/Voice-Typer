"""What the writing AI is NOT trusted with: the signature and the e-mail subject.

A small local model (Qwen 2.5 1.5–7B) follows formatting rules well, but mixes up rules about itself with the
text to write: told "(no signature: don't write one)" it sometimes writes that sentence into the e-mail, and a
rule like "add my signature unless I dictated my own" is beyond it. So:

- sentences of the user's instructions about the signature or the subject are removed before the model sees
  them (`model_instructions`); the preset's two switches decide instead (`preset_flags`);
- the model is told to end with the closing formula and to keep a signature the user dictated;
- `finish_signature` then appends the configured signature, unless the e-mail already ends with one;
- the subject is written by a second, tiny request and put on the first line (`clean_subject`, `with_subject`).
"""

import re

_SIGNATURE_WORDS = re.compile(r"signature|\bsign(?:e|er|ez|é|ed|ing)?\b|\{signature\}", re.I)
_SUBJECT_WORDS = re.compile(r"\bobjets?\b|\btitres?\b|\bsubject\b|\bsubject line\b|\btitle\b", re.I)
_NEGATION = re.compile(r"\b(n['’]|ne\b|pas\b|sans\b|aucun|jamais|no\b|not\b|never\b|without\b|don['’]t\b)", re.I)


def _sentences(text: str) -> list[str]:
    """Lines, then sentences inside each line (keeps list bullets as one unit)."""
    out = []
    for line in text.splitlines():
        parts = re.split(r"(?<=[.!?;])\s+(?=\S)", line)
        out.append(parts)
    return out


def _positive_mention(regex: re.Pattern, text: str) -> bool:
    """True if some mention is not negated just before it: "toujours signer … ne pas mettre la signature"
    has a positive one ("toujours signer"); "sans signature" / "N'écris pas d'objet" have none."""
    for m in regex.finditer(text):
        before = text[max(0, m.start() - 25):m.start()]
        if not _NEGATION.search(before):
            return True
    return False


def wants_signature(instructions: str) -> bool:
    """Old presets (no switch yet): {signature}, or a positive mention of signing."""
    return "{signature}" in instructions or _positive_mention(_SIGNATURE_WORDS, instructions)


def wants_subject(instructions: str) -> bool:
    """Old presets: a positive mention of a subject / title ("génère un titre de courriel")."""
    return _positive_mention(_SUBJECT_WORDS, instructions)


def preset_flags(preset: dict) -> tuple[bool, bool]:
    """(add_signature, subject) of a preset: its switches, or guessed from its instructions."""
    text = preset.get("instructions", "") or ""
    sig = preset.get("add_signature")
    subj = preset.get("subject")
    return (wants_signature(text) if sig is None else bool(sig),
            wants_subject(text) if subj is None else bool(subj))


_SIGNATURE_CLAUSE = re.compile(
    r"\s*,?\s*(?:suivie?s?|followed by)\s+(?:exactement\s+)?(?:de\s+)?(?:this\s+exact\s+|cette\s+|ma\s+|la\s+|"
    r"votre\s+|your\s+|my\s+)?signature\s*:?", re.I)


def model_instructions(instructions: str) -> str:
    """The user's instructions without what concerns the signature or the subject (handled by code).

    "Termine par « Merci, » suivie de cette signature : {signature}" keeps "Termine par « Merci, »"."""
    instructions = _SIGNATURE_CLAUSE.sub("", instructions.replace("{signature}", ""))
    lines = []
    for parts in _sentences(instructions):
        kept = [s for s in parts if not _SIGNATURE_WORDS.search(s) and not _SUBJECT_WORDS.search(s)]
        line = " ".join(kept).strip()
        # a bullet left with nothing but its dash, or a dangling "suivie de :" is dropped too
        if line and not re.fullmatch(r"[-•*\s]*", line):
            lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# ---- signature -------------------------------------------------------------------------------------
_CLOSING = re.compile(r"(merci|cordialement|salutations|bonne (journée|soirée|fin de journée)|au plaisir|"
                      r"à bientôt|bien à vous|amitiés|thanks?|thank you|regards|best|sincerely|cheers)\b", re.I)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.strip().splitlines() if ln.strip()]


def is_closing_line(line: str) -> bool:
    """A short line that is only a closing formula: "Merci,", "Merci et à bientôt !", "Bonne journée,"."""
    line = line.strip()
    if not line or len(line.split()) > 7 or not _CLOSING.match(line) or line.endswith(("?", ":")):
        return False
    rest = _CLOSING.sub(" ", line.lower())
    rest = re.sub(r"\b(et|and|encore|beaucoup|bien|tous|toutes|à|vous|much|again|very|kind|warm|so|"
                  r"you|a|à tous)\b", " ", rest)
    return not re.sub(r"[\W_]+", "", rest)   # nothing left but formulas and punctuation


def _signature_lines(signature: str) -> list[str]:
    """The signature's own lines, without the closing formula some people put in it."""
    return [ln for ln in _lines(signature) if not is_closing_line(ln)]


def ends_with_signature(text: str, signature: str = "") -> bool:
    """True if the e-mail already ends with a signature: the configured one, or a name the user dictated
    after the closing formula ("Merci,\nHugo" / "Bonne journée,\nHugo, pour l'équipe Ventes")."""
    lines = _lines(text)
    if not lines:
        return False
    tail = "\n".join(lines[-4:]).lower()
    first_sig_line = (_signature_lines(signature) or [""])[0].lower()
    if first_sig_line and first_sig_line in tail:
        return True
    last = lines[-1]
    if is_closing_line(last):            # "… Merci et à bientôt !" is a closing, not a signature
        return False
    name = r"[A-ZÀ-Ý][\w'’\-]+(?:\s+[A-ZÀ-Ý][\w'’\-]+){0,3}"
    # "Merci,\nHugo" — a short capitalised line (not a sentence) right after the closing formula
    if len(lines) >= 2 and is_closing_line(lines[-2]) and lines[-2].endswith((",", ".", "!")):
        words = last.split()
        if 1 <= len(words) <= 8 and last[:1].isupper() and not last.endswith((".", "?", ":", "!")):
            return True
    # "Merci, Hugo" / "Bonne journée, Hugo Dasilva" on one line
    m = re.match(rf"^(.*?),\s*({name})\s*$", last)
    return bool(m and _CLOSING.match(m.group(1)) and len(m.group(1).split()) <= 4)


def _drop_trailing_closings(text: str) -> str:
    lines = text.rstrip().splitlines()
    while lines and (not lines[-1].strip() or is_closing_line(lines[-1])):
        lines.pop()
    return "\n".join(lines).rstrip()


def _dedupe_closings(text: str) -> str:
    """The same closing twice near the end ("Merci et à bientôt !" … signature … "Merci et à bientôt !"):
    only the last one stays."""
    lines = text.splitlines()
    start = max(0, len(lines) - 12)
    seen = set()
    for i in range(len(lines) - 1, start - 1, -1):
        if not is_closing_line(lines[i]):
            continue
        key = re.sub(r"[\W_]+", " ", lines[i].lower()).strip()
        if key in seen:
            lines[i] = None
        seen.add(key)
    out = [ln for ln in lines if ln is not None]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def finish_signature(text: str, signature: str, add: bool, blank_line: bool = False) -> str:
    """Appends the configured signature after the closing formula, unless one is already there.

    If the signature has its own closing ("N'hésitez pas à m'appeler…\nMerci et à bientôt !"), the closing the
    AI wrote is removed first: the e-mail ends with the signature's, once.
    blank_line: an empty line between the closing ("Merci,") and the signature (Réglages of the signature)."""
    signature = signature.strip()
    text = text.rstrip()
    if not add or not signature:
        return text
    if ends_with_signature(text, signature):
        return _dedupe_closings(text)
    if any(is_closing_line(ln) for ln in _lines(signature)):
        text = _drop_trailing_closings(text)
    return _dedupe_closings(f"{text}{chr(10) * (2 if blank_line else 1)}{signature}")


# ---- subject ---------------------------------------------------------------------------------------
def clean_subject(raw: str) -> str:
    s = (raw.strip().splitlines() or [""])[0].strip()
    s = re.sub(r"^(objet|subject|titre|title)\s*:\s*", "", s, flags=re.I)
    prev = None
    while prev != s:  # « Titre ». / "Title." / **Title** — peel quotes, stars and the final period
        prev = s
        s = s.strip(" «»\"'“”*\u00a0").rstrip(".").strip()
    return s[:120]


def is_english(text: str) -> bool:
    first = (_lines(text) or [""])[0].lower()
    return bool(re.match(r"(hello|hi|dear|hey|good (morning|afternoon))\b", first))


_EN_WORDS = set("the and i you to is it of that for with my your would like please can we this have are be do "
                "will hi hello thanks thank what how when where there they he she his her our just want need "
                "could should about if not don't i'm it's let me know".split())
_FR_WORDS = set("le la les et je tu vous de des du un une est pour que qui avec mon ma mes votre vos nous pas ce "
                "cette bonjour merci au aux sur dans il elle sont ai fait faire veux voudrais peux pouvez "
                "j'ai c'est s'il n'est qu'il".split())


def detect_language(text: str, default: str = "fr") -> str:
    """"en" or "fr" from the words of a dictation (Whisper may be forced to one language, the user speaks the
    other; the writing AI must answer in the language actually spoken)."""
    words = re.findall(r"[a-zà-ÿ']+", text.lower().replace("’", "'"))
    en = sum(w in _EN_WORDS for w in words)
    fr = sum(w in _FR_WORDS for w in words)
    if en > fr:
        return "en"
    if fr > en:
        return "fr"
    return default if default in ("fr", "en") else "fr"


_GREETING_LINE = re.compile(r"^(bonjour|bonsoir|salut|allô|hello|hi|hey|dear|good (morning|afternoon))\b", re.I)
_GENERIC = {
    "suivi", "information", "informations", "demande", "question", "questions", "mise à jour", "message",
    "courriel", "bonjour", "merci", "objet", "test", "rappel", "urgent", "important", "re", "info", "nouvelles",
    "follow up", "follow-up", "request", "update", "email", "hello", "thanks", "thank you", "reminder", "subject",
}


def subject_source(body: str) -> str:
    """What the subject is about: the e-mail without its greeting, closing and signature."""
    lines = [ln.rstrip() for ln in body.strip().splitlines()]
    while lines and (not lines[0].strip() or _GREETING_LINE.match(lines[0].strip())):
        lines.pop(0)
    for i in range(len(lines) - 1, max(-1, len(lines) - 10), -1):   # cut at the last closing ("Merci,")
        if is_closing_line(lines[i]):
            lines = lines[:i]
            break
    return "\n".join(lines).strip()


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-zà-ÿ0-9]+", text.lower()) if len(w) > 3}


def subject_ok(subject: str, source: str, examples: tuple[str, ...] = ()) -> bool:
    """A subject worth keeping: 3 to 14 words, not generic ("Suivi", "Demande"), about THIS e-mail (most of its
    words come from it — not invented, not copied from the worked examples)."""
    words = subject.split()
    if not 3 <= len(words) <= 14:
        return False
    if re.sub(r"[^\w\s-]", "", subject.lower()).strip() in _GENERIC:
        return False
    stems = _stems(subject)
    if not stems:
        return False
    known = _stems(source)
    if len(stems & known) * 2 < len(stems):
        return False
    return not any(subject.strip().lower() == e.lower() for e in examples)


_SUBJECT_LINE = re.compile(r"^\s*\**\s*(objet|subject|sujet|titre|title)\s*:[^\n]*\n*", re.I)


def strip_subject_line(text: str) -> str:
    """The AI sometimes starts with its own "Objet : …" line: removed (the subject, when wanted, is added
    by code, without any label)."""
    return _SUBJECT_LINE.sub("", text.lstrip(), count=1).lstrip("\n")


_SUBJECT_LABEL = re.compile(r"^\s*\**\s*(objet|subject|sujet)\s*\**\s*:\s*\**\s*(?=\S)", re.I)


def drop_subject_label(text: str) -> str:
    """Last check before the text is typed, whoever wrote it (this PC, or a home PC still running older code):
    "Objet : Visite jeudi" on the first line → "Visite jeudi". Never "Objet :" in front of a subject."""
    if not text:
        return text
    first, sep, rest = text.lstrip().partition("\n")
    label = _SUBJECT_LABEL.match(first)
    if not label:
        return text
    subject = first[label.end():].strip().strip("*").strip()
    return f"{subject}{sep}{rest}" if subject else rest.lstrip("\n")


def with_subject(body: str, subject: str, language: str | None = None) -> str:
    """The subject alone on the first line, then an empty line, then the e-mail — never "Objet :" in front
    (pasted into the subject field or kept as the first line, the label only got in the way)."""
    subject = clean_subject(subject)
    if not subject:
        return body
    return f"{subject}\n\n{body}"
