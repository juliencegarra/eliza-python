"""Recognising the language of an input, and a conversation that follows it.

This is a modern addition, not part of Weizenbaum's program. The method
is deliberately simple and dependency-free, in the spirit of ELIZA: each
input word found in a language's vocabulary (its frequent words plus the
keywords and substitutes of its script) scores one point, and each word
holding a letter typical of the language (é, ç, œ...) one more. The best
score wins; a tie or no evidence keeps the current language.
"""

from __future__ import annotations

from .engine import Eliza
from .languages import Language
from .script import Script
from .text import eliza_uppercase, split_user_input


def vocabulary(language: Language, script: Script | None = None) -> frozenset[str]:
    words = set(language.common_words)
    if script is not None:
        for keyword, rule in script.rules.items():
            words.add(keyword)
            if rule.substitute:
                words.add(rule.substitute)
    return frozenset(words)


def score(text: str, language: Language, vocab: frozenset[str]) -> int:
    words = language.split_elisions(split_user_input(eliza_uppercase(text), ",."))
    points = 0
    for word in words:
        if word in vocab:
            points += 1
        if language.letters and any(ch in language.letters for ch in word):
            points += 1
    return points


def detect(text: str, candidates: dict[str, tuple[Language, frozenset[str]]]) -> str | None:
    """Return the code of the most likely language, or None if undecided."""
    scores = sorted(((score(text, lang, vocab), code) for code, (lang, vocab) in candidates.items()),
                    reverse=True)
    if not scores or scores[0][0] == 0 or (len(scores) > 1 and scores[0][0] == scores[1][0]):
        return None
    return scores[0][1]


class Conversation:
    """One ELIZA per language; each input goes to the one that matches its language.

    Each language keeps its own state (LIMIT, memories, reassembly order),
    as if the user were talking to several monolingual ELIZAs in turn.
    """

    def __init__(self, sessions: dict[str, Eliza], start: str):
        self.sessions = sessions
        self.language = start
        self._candidates = {code: (e.language, vocabulary(e.language, e.script))
                            for code, e in sessions.items()}

    @property
    def current(self) -> Eliza:
        return self.sessions[self.language]

    @property
    def trace(self):
        return self.current.trace

    def hello(self) -> str:
        return self.current.hello()

    def detect(self, text: str) -> str | None:
        return detect(text, self._candidates)

    def response(self, text: str) -> str:
        self.language = self.detect(text) or self.language
        return self.current.response(text)
