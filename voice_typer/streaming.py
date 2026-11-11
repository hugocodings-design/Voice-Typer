"""Typing words into the focused app *while* the user speaks ("live typing").

Every ~0.6 s the engine re-transcribes the last WINDOW_S seconds of the recording (a fixed-size
window keeps each pass fast however long the dictation is). Each pass is a guess whose last words
often change ("je suis" → "je suis allé"), so typing every guess would make the text flicker:

* each pass is lined up with what was already typed by finding the last typed words in it
  (compared without case or punctuation: Whisper often adds a comma or a capital later);
* only the words after that point that two consecutive passes agree on are typed;
* the last word of a pass is held back (it may be cut mid-word), unless the pass is identical
  to the previous one: then the speaker paused and the whole sentence is typed.

When the user releases the key, the full-quality final transcription is compared with what was
typed: only the differing end is erased (Backspace) and retyped.
"""

import re
import string

WINDOW_S = 20
_PUNCT = string.punctuation + "«»“”’…¿¡"


def norm(word: str) -> str:
    return word.strip(_PUNCT).lower()


def _common_prefix(a: list[str], b: list[str]) -> int:
    n = 0
    for x, y in zip(a, b):
        if norm(x) != norm(y):
            break
        n += 1
    return n


def _find(seq: list[str], words: list[str]) -> int:
    """Index just after the LAST occurrence of seq in words (normalised), or -1."""
    target = [norm(w) for w in seq]
    low = [norm(w) for w in words]
    for i in range(len(low) - len(target), -1, -1):
        if low[i:i + len(target)] == target:
            return i + len(target)
    return -1


class LiveTyper:
    """Keeps track of what was typed during one dictation. Not thread-safe: the engine locks."""

    def __init__(self) -> None:
        self.typed = ""                 # exactly what was sent to the app so far
        self._committed: list[str] = []
        self._prev: list[str] | None = None  # previous pass, words after the anchor

    def _after_anchor(self, words: list[str]) -> list[str] | None:
        """The words of this pass that come after what was already typed (None = can't line up)."""
        if not self._committed:
            return words
        for k in (3, 2):  # anchor on the last 3 typed words, else the last 2
            anchor = self._committed[-k:]
            if len(anchor) < k:
                continue
            pos = _find(anchor, words)
            if pos >= 0:
                return words[pos:]
        if len(self._committed) == 1:
            pos = _find(self._committed, words)
            if pos >= 0:
                return words[pos:]
        return None

    def update(self, hypothesis: str, from_start: bool = True) -> str:
        """Feed a new pass; returns the characters to type now ("" if nothing new is certain).

        from_start=False: the pass doesn't cover the beginning of the recording (window), so
        nothing can be typed until something was typed from the start (the final pass does it).
        """
        if not self._committed and not from_start:
            return ""
        after = self._after_anchor(hypothesis.split())
        prev, self._prev = self._prev, after
        if after is None or prev is None or not after:
            return ""
        if len(after) == len(prev) and _common_prefix(prev, after) == len(after):
            stable = after                      # unchanged: the speaker paused, last word included
        else:
            stable = after[:_common_prefix(prev, after[:-1])]
        if not stable:
            return ""
        new = (" " if self.typed else "") + " ".join(stable)
        self.typed += new
        self._committed += stable
        self._prev = after[len(stable):]
        return new

    def finish(self, final: str) -> tuple[int, str]:
        """(number of Backspaces, text to type) turning what was typed into the final text.

        Only the end can be edited (the cursor is after the typed text), so a comma or a capital
        that changed early on is left as typed: erasing everything after it would make the whole
        text flash. Erasing starts at the first word that really differs.
        """
        typed = [(m.end(), m.group()) for m in re.finditer(r"\S+", self.typed)]
        fin = [(m.end(), m.group()) for m in re.finditer(r"\S+", final)]
        i = 0
        while i < min(len(typed), len(fin)) and norm(typed[i][1]) == norm(fin[i][1]):
            i += 1
        if 0 < i and typed[i - 1][1] != fin[i - 1][1] and (i == len(typed) or i == len(fin)):
            i -= 1  # the last kept word must be exact (e.g. the final adds a period to it)
        if i == 0:
            return len(self.typed), final
        kept = typed[i - 1][0]
        return len(self.typed) - kept, final[fin[i - 1][0]:]
