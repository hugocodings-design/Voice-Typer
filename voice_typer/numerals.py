"""Numbers said in words → digits ("vingt-cinq" → "25", "trois virgule cinq pour cent" → "3,5 %").

Whisper writes most numbers in digits already, but not always ("deux", "quatre-vingt-dix-sept",
"twenty twenty-four"). Applied after the filler clean-up, before dictionary replacements and voice commands
(so "trois virgule cinq" becomes "3,5" rather than "3, 5"). Shared rules with nothing else: pure text.

Left in words on purpose:
- "un" / "une" / "one" alone (articles: "un rendez-vous", "one of them"), "mille" alone ("mille mercis"),
  "zéro" / "zero" alone ("repartir à zéro") — converted when other numbers follow ("un deux trois",
  "zéro six"), or before "pour cent" / "virgule";
- "neuf" when it means *new* ("un vélo neuf"): converted only when a noun follows ("neuf heures");
- words joined to another word by a hyphen ("deux-roues", "trois-quarts").
Two numbers said one after the other stay separate ("deux trois" → "2 3"), except English years
("nineteen eighty-four" → "1984", "twenty twenty-four" → "2024").
"""

import re

_FR = {
    "zéro": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
    "seize": 16, "vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
    "septante": 70, "huitante": 80, "octante": 80, "nonante": 90, "cent": 100, "cents": 100, "mille": 1000,
    "million": 10**6, "millions": 10**6, "milliard": 10**9, "milliards": 10**9,
}
_EN = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
    "million": 10**6, "millions": 10**6, "billion": 10**9, "billions": 10**9,
}
_BIG = (1000, 10**6, 10**9)
_HUNDRED_WORDS = {"cent", "cents", "hundred"}
_BIG_WORDS = {"mille", "thousand", "million", "millions", "milliard", "milliards", "billion", "billions"}
_ALONE_KEPT = {"un", "une", "one", "mille", "zéro", "zero"}
_PERCENT_NEXT = {"pour", "pourcent", "pourcents", "percent"}
# after "neuf", these words mean it was the adjective ("un vélo neuf et rapide")
_FUNCTION_WORDS = {
    "et", "ou", "mais", "que", "qui", "comme", "pour", "à", "a", "de", "du", "des", "en", "dans", "sur", "avec",
    "sans", "chez", "par", "le", "la", "les", "un", "une", "ce", "cette", "il", "elle", "je", "tu", "on",
    "nous", "vous", "ils", "elles", "est", "sont", "était", "aussi", "pas", "plus", "très", "non", "oui",
}

_TOKEN = re.compile(r"[^\W\d_]+(?:[-‑][^\W\d_]+)*|\d+|\s+|.", re.S)
_HYPHEN = re.compile(r"[-‑]")


def _vocab(language: str | None) -> list[tuple[str, dict]]:
    if language == "fr":
        return [("fr", _FR)]
    if language == "en":
        return [("en", _EN)]
    return [("fr", _FR), ("en", _EN)]


def _lookup(word: str, vocabs) -> tuple[int, str] | None:
    w = word.lower()
    for lang, table in vocabs:
        if w in table:
            return table[w], lang
    return None


def _word_items(token: str, vocabs) -> list[tuple[str, int, str]] | None:
    """[(word, value, lang)] for a number token ("quatre-vingt-dix", "trente-et-un"), else None."""
    if not token[:1].isalpha():
        return None
    parts = _HYPHEN.split(token)
    items = []
    for p in parts:
        if p.lower() == "et" and len(parts) >= 3:
            continue
        hit = _lookup(p, vocabs)
        if not hit:
            return None
        items.append((p.lower(), hit[0], hit[1]))
    return items or None


class _Number:
    """One number read word by word (French and English grammar of numbers)."""

    def __init__(self):
        self.total = 0       # thousands / millions already closed
        self.current = 0     # below the last big multiplier
        self.last_big = 0
        self.big_word = ""   # "millions" in "deux millions": kept as a word when the number is round
        self.last_word = ""
        self.last_lang = ""
        self.words: list[str] = []

    def copy(self) -> "_Number":
        n = _Number()
        n.__dict__.update(self.__dict__)
        n.words = list(self.words)
        return n

    @property
    def value(self) -> int:
        return self.total + self.current

    def can_take(self, word: str, v: int, lang: str) -> bool:
        if not self.words:
            return True
        if v == 0 or self.last_word in ("zéro", "zero"):
            return False
        r = self.current % 100
        if v == 100:
            if word in ("cent", "cents") and self.last_lang != "fr" and self.last_word not in _BIG_WORDS:
                return False   # "fifty cents" is money
            return self.current < 100 and self.last_word not in _HUNDRED_WORDS
        if v in _BIG:
            return (self.last_big == 0 or v < self.last_big) and self.last_word not in _BIG_WORDS
        if v == 20 and self.last_word == "quatre" and r == 4:   # quatre-vingt(s)
            return True
        if r == 0:
            return True                                         # "cent deux", "mille trois", "two thousand five"
        if r >= 20 and r % 10 == 0 and v < 10:                  # vingt-deux, twenty-one
            return True
        if r in (60, 80) and 10 <= v < 20 and lang == "fr":     # soixante-douze, quatre-vingt-dix
            return True
        return r == 10 and v in (7, 8, 9) and self.last_word == "dix"   # dix-sept

    def take(self, word: str, v: int, lang: str) -> None:
        if v == 100:
            self.current = (self.current or 1) * 100
        elif v in _BIG:
            self.total += (self.current or 1) * v
            self.current = 0
            self.last_big = v
            self.big_word = word if v >= 10**6 else ""
        elif v == 20 and self.last_word == "quatre" and self.current % 100 == 4:
            self.current += 76
        else:
            self.current += v
        self.last_word, self.last_lang = word, lang
        self.words.append(word)

    def text(self, lang: str) -> str:
        value = self.value
        if self.big_word and value % self.last_big == 0:
            return f"{_group(value // self.last_big, lang)} {self.big_word}"   # "2 millions", "1 million"
        return _group(value, lang)


def _group(value: int, lang: str) -> str:
    if value < 10000:
        return str(value)      # years and small numbers: "2024", "1500"
    s = f"{value:,}"
    return s.replace(",", "\u00a0") if lang == "fr" else s   # "12 500" never cut at a line end


class _Reader:
    def __init__(self, text: str, language: str | None):
        self.tokens = _TOKEN.findall(text)
        self.vocabs = _vocab(language)
        self.language = language

    def next_word(self, j: int) -> tuple[str, int]:
        while j < len(self.tokens) and self.tokens[j].isspace():
            j += 1
        return (self.tokens[j].lower(), j) if j < len(self.tokens) else ("", j)

    def read(self, i: int) -> tuple[_Number, int] | None:
        """The longest number starting at token i: (number, index after its last token)."""
        tokens = self.tokens
        num = _Number()
        j = end = i
        if tokens[i].lower() == "a" and self.language != "fr":            # "a hundred", "a thousand"
            nxt, _ = self.next_word(i + 1)
            if nxt not in ("hundred", "thousand", "million", "billion"):
                return None
            num.take("a", 1, "en")
            j = end = i + 1
        while j < len(tokens):
            t = tokens[j]
            if t.isspace():
                j += 1
                continue
            low = t.lower()
            if low in ("et", "and") and num.words:   # "vingt et un", "soixante et onze", "a hundred and five"
                nxt, _ = self.next_word(j + 1)
                r = num.current % 100
                if low == "et" and r in (20, 30, 40, 50, 60) and nxt in ("un", "une", "onze"):
                    j += 1
                    continue
                hit = _lookup(nxt, [("en", _EN)])
                if low == "and" and num.value and r == 0 and hit and 0 < hit[0] < 100:
                    j += 1
                    continue
                break
            items = _word_items(t, self.vocabs)
            if not items:
                break
            trial = num.copy()
            if not all(trial.can_take(w, v, lg) and (trial.take(w, v, lg) or True) for w, v, lg in items):
                break
            num = trial
            j = end = j + 1
        return (num, end) if num.words and end > i else None

    def starts_number(self, j: int) -> bool:
        nxt, k = self.next_word(j)
        return bool(nxt) and (nxt.isdigit() or bool(_word_items(self.tokens[k], self.vocabs)))

    def keep_in_words(self, num: _Number, start: int, end: int, out: list[str]) -> bool:
        if len(num.words) != 1:
            return False
        word = num.words[0]
        prev = next((t for t in reversed(out) if not t.isspace()), "").lower()
        if word in ("cent", "cents") and (prev == "pour" or prev.isdigit() or word == "cents"):
            return True   # "cinquante pour cent" → 50 %; "fifty cents" is money
        nxt, k = self.next_word(end)
        if word == "neuf":   # "neuf heures" → 9 heures; "un vélo neuf" / "neuf et rapide" stay
            return not nxt[:1].isalpha() or nxt in _FUNCTION_WORDS
        if word not in _ALONE_KEPT:
            return False
        if nxt in _PERCENT_NEXT or nxt in ("virgule", "point") and self.starts_number(k + 1):
            return False
        if word == "mille":
            return True
        if self.starts_number(end):           # "un deux trois", "zéro six douze"
            return False
        if word in ("zéro", "zero"):          # "… six zéro"
            return not prev.isdigit()
        return True


def to_digits(text: str, language: str | None) -> str:
    rd = _Reader(text, language)
    tokens = rd.tokens
    out: list[str] = []
    i = 0
    while i < len(tokens):
        got = rd.read(i) if tokens[i][:1].isalpha() else None
        if not got:
            out.append(tokens[i])
            i += 1
            continue
        num, end = got
        lang = num.last_lang or "fr"
        # English years said in two halves: "nineteen eighty-four", "twenty twenty-four"
        if lang == "en" and num.value in (19, 20) and len(num.words) == 1:
            nxt, k = rd.next_word(end)
            after = rd.read(k) if nxt[:1].isalpha() else None
            if after and after[0].last_lang == "en" and 10 <= after[0].value <= 99 and not after[0].last_big:
                out.append(str(num.value * 100 + after[0].value))
                i = after[1]
                continue
        if rd.keep_in_words(num, i, end, out):
            out.extend(tokens[i:end])
        else:
            out.append(num.text(lang))
        i = end
    return _decimals("".join(out), language)


def _decimals(text: str, language: str | None) -> str:
    if language != "en":
        text = re.sub(r"\b(\d+) virgule (\d+)\b", r"\1,\2", text, flags=re.I)
        text = re.sub(r"\b(\d+(?:,\d+)?) ?(?:pour ?cents?|pourcents?)\b", "\\1\u00a0%", text, flags=re.I)
    if language != "fr":
        text = re.sub(r"\b(\d+) point (\d+)\b", r"\1.\2", text, flags=re.I)
        text = re.sub(r"\b(\d+(?:\.\d+)?) ?percent\b", r"\1%", text, flags=re.I)
    return text
