"""Typing words into the focused app *while* the user speaks ("live typing").

Whisper re-transcribes the whole recording every ~0.6 s and the last words often change
("je suis" → "je suis allé"). Typing every guess would make the text flicker, so only words
that two consecutive passes agree on are typed (the last word of a pass is never trusted, it
may be cut mid-word). When the user releases the key, the full-quality final transcription
is compared with what was typed: only the differing end is erased (Backspace) and retyped.
"""


def stable_prefix(prev: list[str], cur: list[str]) -> list[str]:
    """Words both passes agree on, from the start; the current pass's last word is excluded."""
    out = []
    for a, b in zip(prev, cur[:-1]):
        if a != b:
            break
        out.append(b)
    return out


class LiveTyper:
    """Keeps track of what was typed during one dictation. Not thread-safe: the engine locks."""

    def __init__(self) -> None:
        self.typed = ""             # exactly what was sent to the app so far
        self._committed: list[str] = []
        self._prev: list[str] = []

    def update(self, hypothesis: str) -> str:
        """Feed a new pass; returns the characters to type now ("" if nothing new is certain)."""
        cur = hypothesis.split()
        stable = stable_prefix(self._prev, cur)
        self._prev = cur
        # only grow: never take back words already typed (the final pass fixes them)
        if len(stable) <= len(self._committed) or stable[:len(self._committed)] != self._committed:
            return ""
        self._committed = stable
        text = " ".join(stable)
        new = text[len(self.typed):]
        self.typed = text
        return new

    def finish(self, final: str) -> tuple[int, str]:
        """(number of Backspaces, text to type) turning what was typed into the final text."""
        p = 0
        limit = min(len(self.typed), len(final))
        while p < limit and self.typed[p] == final[p]:
            p += 1
        return len(self.typed) - p, final[p:]
