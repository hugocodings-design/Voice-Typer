"""Spoken commands turned into formatting: "à la ligne" → line break, "virgule" → ",", etc.

Applied to the transcript right after Whisper (and before any AI rewriting). Only phrases that are
very unlikely in normal speech are commands ("deux points" is not one: "j'ai deux points à voir").
Whisper often adds its own punctuation around a command ("Bonjour, à la ligne. Merci"): it is absorbed.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    phrases: tuple[str, ...]  # spoken forms (lowercase, accents as Whisper writes them)
    output: str               # what is inserted
    kind: str                 # "break" (line/paragraph), "punct" (attached to previous word),
    #                           "open" (attached to next word), "close" (attached to previous word)
    label_fr: str = ""
    label_en: str = ""


COMMANDS: dict[str, list[Command]] = {
    "fr": [
        Command(("nouveau paragraphe",), "\n\n", "break", "Nouveau paragraphe (ligne vide)"),
        Command(("à la ligne", "retour à la ligne", "nouvelle ligne"), "\n", "break", "Retour à la ligne"),
        Command(("point à la ligne",), ".\n", "break", "Point + retour à la ligne"),
        Command(("point d'interrogation",), " ?", "punct", "?"),
        Command(("point d'exclamation",), " !", "punct", "!"),
        Command(("point-virgule", "point virgule"), " ;", "punct", ";"),
        Command(("virgule",), ",", "punct", ","),
        Command(("point final",), ".", "punct", "."),
        Command(("points de suspension",), "…", "punct", "…"),
        Command(("ouvrez les guillemets", "ouvrir les guillemets", "ouvre les guillemets"), "« ", "open", "«"),
        Command(("fermez les guillemets", "fermer les guillemets", "ferme les guillemets"), " »", "close", "»"),
        Command(("ouvrez la parenthèse", "ouvrir la parenthèse", "ouvre la parenthèse"), "(", "open", "("),
        Command(("fermez la parenthèse", "fermer la parenthèse", "ferme la parenthèse"), ")", "close", ")"),
    ],
    "en": [
        Command(("new paragraph",), "\n\n", "break", label_en="New paragraph (blank line)"),
        Command(("new line", "next line"), "\n", "break", label_en="Line break"),
        Command(("question mark",), "?", "punct", label_en="?"),
        Command(("exclamation mark", "exclamation point"), "!", "punct", label_en="!"),
        Command(("semicolon",), ";", "punct", label_en=";"),
        Command(("comma",), ",", "punct", label_en=","),
        Command(("full stop",), ".", "punct", label_en="."),
        Command(("ellipsis",), "…", "punct", label_en="…"),
        Command(("open quote", "open quotes"), "“", "open", label_en="“"),
        Command(("close quote", "close quotes", "end quote"), "”", "close", label_en="”"),
        Command(("open parenthesis", "open bracket"), "(", "open", label_en="("),
        Command(("close parenthesis", "close bracket"), ")", "close", label_en=")"),
    ],
}

_PUNCT = r"[,;:.!?…]"


def _phrase_regex(phrase: str) -> str:
    # spaces/hyphens/apostrophes as Whisper may write them: "point-virgule", "point d’interrogation"
    parts = re.split(r"[\s\-]+", phrase)
    return r"[\s\-]+".join(re.escape(p).replace("'", "['’]") for p in parts)


def _compile(lang: str) -> list[tuple[re.Pattern, Command]]:
    out = []
    cmds = sorted(COMMANDS.get(lang, []), key=lambda c: -max(len(p) for p in c.phrases))  # longest first
    for c in cmds:
        alt = "|".join(_phrase_regex(p) for p in sorted(c.phrases, key=len, reverse=True))
        # absorb Whisper's own punctuation/spaces around the command
        if c.kind == "break":     # keep the comma before ("Bonjour,\n"), drop Whisper's period after
            pat = rf"[ \t]*\b(?:{alt})\b[ \t]*{_PUNCT}?[ \t]*"
        elif c.kind == "close":   # the punctuation after a closing quote/parenthesis is a real sentence end
            pat = rf"[ \t]*{_PUNCT}?[ \t]*\b(?:{alt})\b"
        else:
            pat = rf"[ \t]*{_PUNCT}?[ \t]*\b(?:{alt})\b[ \t]*{_PUNCT}?[ \t]*"
        out.append((re.compile(pat, re.IGNORECASE), c))
    return out


_CACHE: dict[str, list] = {}


def apply(text: str, language: str | None) -> str:
    """Replace spoken commands in `text`. language None (auto) tries French then English."""
    if not text:
        return text
    langs = [language] if language in COMMANDS else ["fr", "en"]
    for lang in langs:
        rules = _CACHE.setdefault(lang, _compile(lang))
        for pat, cmd in rules:
            sep = {"break": "", "punct": " ", "open": "", "close": " "}[cmd.kind]
            if cmd.kind == "open":
                text = pat.sub(lambda _m, c=cmd: " " + c.output, text)
            else:
                text = pat.sub(lambda _m, c=cmd, s=sep: c.output + s, text)
    return _tidy(text)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)            # no trailing spaces before a break
    text = re.sub(r"\n[ \t]+", "\n", text)            # no leading spaces after a break
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"([(«“])\s+(?=\S)", lambda m: m.group(1) + (" " if m.group(1) == "«" else ""), text)
    text = re.sub(r"(?<=\S)\s+([)”])", r"\1", text)
    text = re.sub(r",(?=[.!?…])", "", text)           # "mot,." → "mot."
    text = re.sub(r"(?<=[»”)]) +(?=[.,…])", "", text)  # "« bonjour » ." → "« bonjour »."
    text = re.sub(r" +$", "", text, flags=re.M)
    # capital letter at the start of each line / after sentence end
    text = re.sub(r"(^|\n|[.!?…]\s)([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), text)
    return text.strip(" \t")


UNDO_PHRASES = {
    "fr": ("efface ça", "efface cela", "efface ca", "annule ça", "annule la dernière dictée", "supprime ça"),
    "en": ("delete that", "scratch that", "undo that", "erase that"),
}


def _bare(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s'’]", " ", text.lower().replace("-", " ")).split())


def is_undo(text: str, language: str | None) -> bool:
    """True when the WHOLE dictation is just « efface ça » (said alone, so it can't be a sentence
    that merely contains those words)."""
    bare = _bare(text)
    if not bare or len(bare) > 40:
        return False
    langs = [language] if language in UNDO_PHRASES else list(UNDO_PHRASES)
    return any(bare == _bare(p) for lang in langs for p in UNDO_PHRASES[lang])


def reference(ui: str) -> list[tuple[str, str]]:
    """(what to say, what you get) rows for the help page, in the interface language."""
    lang = "fr" if ui == "fr" else "en"
    rows = []
    for c in COMMANDS[lang]:
        label = c.label_fr if lang == "fr" else c.label_en
        shown = c.phrases[:2]  # the table stays readable; the other variants work too
        rows.append((" / ".join(f"« {p} »" if lang == "fr" else f"“{p}”" for p in shown), label))
    undo = UNDO_PHRASES[lang][:1] + UNDO_PHRASES[lang][1:2]
    rows.append((" / ".join(f"« {p} »" if lang == "fr" else f"“{p}”" for p in undo),
                 "Efface la dernière dictée (dit seul)" if lang == "fr" else "Deletes the last dictation (said alone)"))
    return rows
