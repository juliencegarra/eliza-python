"""Reader for the 1966 ELIZA script format (S-expressions).

    eliza_script    : opening_remarks ['START'] rules ['(' ')'] ;
    keyword_rule    : '(' keyword ['=' substitute] ['DLIST' '(' tags ')']
                          [precedence] {transformation} [reference] ')' ;
    transformation  : '(' '(' decomposition ')' reassembly {reassembly} ')' ;
    reassembly      : '(' words ')' | '(' '=' keyword ')' | '(' 'NEWKEY' ')'
                    | '(' 'PRE' '(' words ')' '(' '=' keyword ')' ')' ;
    memory_rule     : '(' 'MEMORY' keyword 4 * ('(' decomposition '=' words ')') ')' ;
    none_rule       : '(' 'NONE' '(' '(' '0' ')' reassembly {reassembly} ')' ')' ;

A ';' starts a comment to the end of the line. The grammar and the checks
follow Anthony Hay's eliza.cpp, whose reader accepts the published DOCTOR
script, the 1965 MIT listings (TAPE 100) and his Turing machine scripts.

Scripts may carry optional metadata in comments, ignored by other ELIZAs:

    ; eliza-language: fr
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .text import eliza_uppercase, to_int

MEMORY_TRANSFORMATIONS = 4  # "exactly four transformations" [CACM p. 41]

_PRAGMA = re.compile(r"^\s*;\s*eliza-(\w+)\s*:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)


class ScriptError(ValueError):
    pass


@dataclass(frozen=True)
class Reassembly:
    """One reassembly rule.

    kind is "words" (plain reply), "link" (=KEYWORD), "newkey" or "pre"
    (PRE: rebuild the input with words, then apply keyword's rules).
    """
    kind: str
    words: tuple[str, ...] = ()
    keyword: str = ""


@dataclass(frozen=True)
class Transformation:
    decomposition: tuple[str, ...]
    reassemblies: tuple[Reassembly, ...]


@dataclass(frozen=True)
class KeywordRule:
    keyword: str
    substitute: str = ""
    precedence: int = 0
    tags: tuple[str, ...] = ()
    transformations: tuple[Transformation, ...] = ()
    link: str = ""  # trailing (=KEYWORD) used when no decomposition matches

    @property
    def has_transformation(self) -> bool:
        return bool(self.transformations or self.link)


@dataclass(frozen=True)
class MemoryRule:
    keyword: str
    transformations: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]


@dataclass
class Script:
    hello: list[str]
    rules: dict[str, KeywordRule]
    none: KeywordRule
    memory: MemoryRule
    metadata: dict[str, str] = field(default_factory=dict)

    def tags(self) -> dict[str, list[str]]:
        """DLIST tags -> keywords, e.g. "FAMILY" -> ["MOTHER", "FATHER", ...]."""
        tags: dict[str, list[str]] = {}
        for keyword in sorted(self.rules):
            for t in self.rules[keyword].tags:
                if t == "/":
                    continue
                if len(t) > 1 and t.startswith("/"):
                    t = t[1:]
                tags.setdefault(t, []).append(keyword)
        return tags


# --------------------------------------------------------------------------
# tokenizer

_EOF, _SYMBOL, _NUMBER, _OPEN, _CLOSE = "eof", "symbol", "number", "(", ")"


def _is_space(ch: str) -> bool:
    return ch <= " " or ch == "\x7f"


class _Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self._peeked = None

    def peek(self):
        if self._peeked is None:
            self._peeked = self._read()
        return self._peeked

    def next(self):
        tok = self.peek()
        self._peeked = None
        return tok

    def _read(self):
        text, n = self.text, len(self.text)
        while True:
            while self.pos < n and _is_space(text[self.pos]):
                if text[self.pos] == "\n":
                    self.line += 1
                self.pos += 1
            if self.pos < n and text[self.pos] == ";":
                while self.pos < n and text[self.pos] != "\n":
                    self.pos += 1
                continue
            break
        if self.pos >= n:
            return (_EOF, "")
        ch = text[self.pos]
        self.pos += 1
        if ch == "(":
            return (_OPEN, "")
        if ch == ")":
            return (_CLOSE, "")
        if ch == "=":
            return (_SYMBOL, "=")
        if "0" <= ch <= "9":
            start = self.pos - 1
            while self.pos < n and "0" <= text[self.pos] <= "9":
                self.pos += 1
            return (_NUMBER, text[start:self.pos])
        start = self.pos - 1
        while self.pos < n and not (text[self.pos] in "();=" or _is_space(text[self.pos])):
            self.pos += 1
        return (_SYMBOL, eliza_uppercase(text[start:self.pos]))


# --------------------------------------------------------------------------
# reader

def _indexes_valid(decomposition, words) -> str:
    for w in words:
        n = to_int(w)
        if n >= 0 and (n == 0 or n > len(decomposition)):
            return f"reassembly index '{n}' out of range [1..{len(decomposition)}]"
    return ""


class _Reader:
    def __init__(self, text: str):
        self.tok = _Tokenizer(text)
        self.rules: dict[str, KeywordRule] = {}
        self.none: KeywordRule | None = None
        self.memory: MemoryRule | None = None
        self.references: list[tuple[int, str]] = []

    def error(self, msg: str) -> ScriptError:
        return ScriptError(f"Script error on line {self.tok.line}: {msg}")

    def rdlist(self, prior: bool = True) -> list[str]:
        """Words up to ')'; a sublist becomes one "(A B C)" string."""
        t = self.tok.next()
        if prior:
            if t[0] != _OPEN:
                raise self.error("expected '('")
            t = self.tok.next()
        out = []
        while t[0] != _CLOSE:
            if t[0] in (_SYMBOL, _NUMBER):
                out.append(t[1])
            elif t[0] == _OPEN:
                sub = []
                t = self.tok.next()
                while t[0] != _CLOSE:
                    if t[0] != _SYMBOL:
                        raise self.error("expected symbol")
                    sub.append(t[1])
                    t = self.tok.next()
                out.append("(" + " ".join(sub) + ")")
            else:
                raise self.error("expected ')'")
            t = self.tok.next()
        return out

    def read(self) -> Script:
        hello = self.rdlist()
        if self.tok.peek() == (_SYMBOL, "START"):
            self.tok.next()
        while self.read_rule():
            pass
        if self.none is None:
            raise ScriptError("Script error: no NONE rule specified; see Jan 1966 CACM page 41")
        if self.memory is None:
            raise ScriptError("Script error: no MEMORY rule specified; see Jan 1966 CACM page 41")
        if self.memory.keyword not in self.rules:
            raise ScriptError(
                f"Script error: MEMORY rule keyword '{self.memory.keyword}' is not also "
                "a keyword in its own right; see Jan 1966 CACM page 41")
        for line, keyword in self.references:
            rule = self.rules.get(keyword)
            if rule is None:
                raise ScriptError(
                    f"Script error on line {line}: '={keyword}' referenced keyword does not exist")
            if not rule.has_transformation:
                raise ScriptError(
                    f"Script error on line {line}: '={keyword}' referenced keyword "
                    "has no associated transformation rules")
        return Script(hello, self.rules, self.none, self.memory)

    def read_rule(self) -> bool:
        t = self.tok.next()
        if t[0] == _EOF:
            return False
        if t[0] != _OPEN:
            raise self.error("expected '('")
        t = self.tok.peek()
        if t[0] == _CLOSE:
            self.tok.next()
            return True  # the empty list ending the script
        if t[0] != _SYMBOL:
            raise self.error("expected keyword|MEMORY|NONE")
        if t[1] == "MEMORY":
            self.read_memory_rule()
        else:
            self.read_keyword_rule()
        return True

    def read_memory_rule(self) -> None:
        form = ("; expected form is (MEMORY keyword (decomp1=reassm1)(decomp2=reassm2)"
                "(decomp3=reassm3)(decomp4=reassm4))")
        self.tok.next()  # MEMORY
        if self.memory is not None:
            raise self.error("MEMORY rule already specified")
        t = self.tok.next()
        if t[0] != _SYMBOL:
            raise self.error("expected keyword to follow MEMORY" + form)
        keyword = t[1]
        transformations = []
        for _ in range(MEMORY_TRANSFORMATIONS):
            if self.tok.next()[0] != _OPEN:
                raise self.error("expected '('" + form)
            decomposition = []
            t = self.tok.next()
            while t != (_SYMBOL, "=") and t[0] != _EOF:
                decomposition.append(t[1])
                t = self.tok.next()
            if not decomposition:
                raise self.error("expected 'decompose_terms = reassemble_terms'" + form)
            if t != (_SYMBOL, "="):
                raise self.error("expected '='" + form)
            reassembly = []
            t = self.tok.next()
            while t[0] not in (_CLOSE, _EOF):
                reassembly.append(t[1])
                t = self.tok.next()
            if not reassembly:
                raise self.error("expected 'decompose_terms = reassemble_terms'" + form)
            if t[0] != _CLOSE:
                raise self.error("expected ')'" + form)
            msg = _indexes_valid(decomposition, reassembly)
            if msg:
                raise self.error(msg)
            transformations.append((tuple(decomposition), tuple(reassembly)))
        if self.tok.next()[0] != _CLOSE:
            raise self.error("expected ')'" + form)
        self.memory = MemoryRule(keyword, tuple(transformations))

    def read_reassembly(self) -> Reassembly:
        if self.tok.next()[0] != _OPEN:
            raise self.error("expected '('")
        if self.tok.peek() != (_SYMBOL, "PRE"):
            words = self.rdlist(prior=False)
            if words and words[0] == "=":
                if len(words) != 2:
                    raise self.error("expected reference keyword to follow '='")
                self.references.append((self.tok.line, words[1]))
                return Reassembly("link", keyword=words[1])
            if words == ["NEWKEY"]:
                return Reassembly("newkey")
            return Reassembly("words", tuple(words))
        self.tok.next()  # PRE
        words = self.rdlist()
        reference = self.rdlist()
        if len(reference) != 2 or reference[0] != "=":
            raise self.error("expected '(=reference)' in PRE rule")
        self.references.append((self.tok.line, reference[1]))
        if self.tok.next()[0] != _CLOSE:
            raise self.error("expected ')'")
        return Reassembly("pre", tuple(words), reference[1])

    def read_keyword_rule(self) -> None:
        keyword = self.tok.next()[1]
        is_none = keyword == "NONE"
        if keyword in self.rules or (is_none and self.none is not None):
            raise self.error(f"keyword rule already specified for keyword '{keyword}'")
        if self.tok.peek()[0] == _CLOSE:
            raise self.error(f"keyword '{keyword}' has no associated body")

        substitute, precedence, tags, link = "", 0, [], ""
        transformations = []
        t = self.tok.next()
        while t[0] != _CLOSE:
            if t == (_SYMBOL, "="):
                t = self.tok.next()
                if t[0] != _SYMBOL:
                    raise self.error("expected keyword")
                substitute = t[1]
            elif t[0] == _NUMBER:
                precedence = int(t[1])
            elif t == (_SYMBOL, "DLIST"):
                tags = self.rdlist()
            elif t[0] == _OPEN:
                if self.tok.peek() == (_SYMBOL, "="):
                    # a reference: (=KEYWORD), which must end the rule
                    self.tok.next()
                    t = self.tok.next()
                    if t[0] != _SYMBOL:
                        raise self.error("expected equivalence class name")
                    link = t[1]
                    self.references.append((self.tok.line, link))
                    if self.tok.next()[0] != _CLOSE or self.tok.peek()[0] != _CLOSE:
                        raise self.error("expected ')'")
                else:
                    decomposition = self.rdlist()
                    if not decomposition:
                        raise self.error("decompose pattern cannot be empty")
                    reassemblies = []
                    while True:
                        r = self.read_reassembly()
                        msg = _indexes_valid(decomposition, r.words)
                        if msg:
                            raise self.error(msg)
                        reassemblies.append(r)
                        if self.tok.peek()[0] != _OPEN:
                            break
                    if self.tok.next()[0] != _CLOSE:
                        raise self.error("expected ')'")
                    transformations.append(Transformation(tuple(decomposition), tuple(reassemblies)))
            else:
                raise self.error("malformed rule")
            t = self.tok.next()

        rule = KeywordRule(keyword, substitute, precedence, tuple(tags), tuple(transformations), link)
        if is_none:
            self.none = rule  # kept apart: the input word NONE is not this rule
        else:
            self.rules[keyword] = rule


def parse(text: str) -> Script:
    """Parse the text of an ELIZA script."""
    if text.startswith("﻿"):
        text = text[1:]
    script = _Reader(text.replace("\r\n", "\n").replace("\r", "\n")).read()
    script.metadata = {k.lower(): v for k, v in _PRAGMA.findall(text)}
    return script


def load(path: str | Path) -> Script:
    """Read a UTF-8 script file."""
    return parse(Path(path).read_text(encoding="utf-8"))
