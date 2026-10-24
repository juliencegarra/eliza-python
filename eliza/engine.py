"""The ELIZA algorithm.

This follows the 1966 CACM description as reconstructed by Anthony Hay
(eliza.cpp), including what the MAD-SLIP listing of March 1965 revealed:

- BUT is a delimiter, like the comma and the period;
- "a certain counting mechanism" is LIMIT, cycling 1, 2, 3, 4: a memory
  is recalled only when LIMIT is 4 and the input has no keyword;
- the MEMORY transformation is chosen by HASH of the last input cell,
  not at random, so conversations are reproducible;
- a keyword whose decompositions all fail gives one of four built-in
  messages, chosen by LIMIT.

Unlike eliza.cpp the per-rule state (which reassembly comes next) is kept
in the Eliza object, so one Script can serve several conversations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .hollerith import last_chunk_as_bcd, slip_hash
from .languages import ENGLISH, Language
from .match import match, reassemble
from .script import KeywordRule, Script
from .text import eliza_uppercase, fold_accents, join, split_user_input

# punctuation that can be a delimiter: the 7094 BCD set, less the space
_BCD_PUNCTUATION = "='+.)-$*/,("


@dataclass
class Trace:
    """What ELIZA did to produce the last response (for the * command)."""
    lines: list[str] = field(default_factory=list)

    def __call__(self, line: str) -> None:
        self.lines.append(line)

    def text(self) -> str:
        return "\n".join(" | " + line for line in self.lines)


class Eliza:
    def __init__(
        self,
        script: Script,
        language: Language = ENGLISH,
        *,
        use_nomatch_msgs: bool = True,
        on_newkey_fail_use_none: bool = True,
        fold_input_accents: bool = False,
    ):
        """
        language                 delimiters and built-in messages (see languages.py)
        use_nomatch_msgs         True: script errors give the built-in messages, as
                                 Weizenbaum's code did; False: use the NONE rule
        on_newkey_fail_use_none  NEWKEY with an empty keystack uses NONE [CACM p. 41]
                                 (the Quarton study suggests a built-in message)
        fold_input_accents       remove accents from the input; only useful with a
                                 script whose words were folded the same way
        """
        self.script = script
        self.language = language
        self.use_nomatch_msgs = use_nomatch_msgs
        self.on_newkey_fail_use_none = on_newkey_fail_use_none
        self.fold_input_accents = fold_input_accents
        self.tags = script.tags()
        self.delimiters = set(language.delimiters)
        self.punctuation = "".join(
            d for d in language.delimiters if len(d) == 1 and d in _BCD_PUNCTUATION)
        self.limit = 1          # Weizenbaum's LIMIT
        self.memories: list[str] = []
        self._next: dict[tuple[str, int], int] = {}  # next reassembly per decomposition
        self.trace = Trace()

    def hello(self) -> str:
        return join(self.script.hello)

    def nomatch(self) -> str:
        return self.language.nomatch_messages[self.limit - 1]

    def words(self, text: str) -> list[str]:
        """The input as ELIZA sees it: "Hello, world!" -> HELLO , WORLD ."""
        text = eliza_uppercase(text)
        if self.fold_input_accents:
            text = fold_accents(text)
        return self.language.split_elisions(split_user_input(text, self.punctuation))

    # ----------------------------------------------------------------------

    def response(self, text: str) -> str:
        return self.language.join_elisions(self._response(text))

    def _response(self, text: str) -> str:
        self.trace = trace = Trace()
        words = self.words(text)
        trace("input: " + join(words))

        self.limit = self.limit % 4 + 1
        trace(f"LIMIT: {self.limit} ({self.nomatch()})")

        # scan for keywords, keeping only the first clause holding one
        # [CACM p. 37]; build the keystack; apply substitutions [p. 39]
        keystack: list[str] = []
        top_rank = 0
        i = 0
        while i < len(words):
            word = words[i]
            if word in self.delimiters:
                if not keystack:
                    trace("discard: " + join(words[:i + 1]))
                    del words[:i + 1]
                    i = 0
                    continue
                del words[i:]
                break
            rule = self.script.rules.get(word)
            if rule is not None:
                if rule.has_transformation:
                    if rule.precedence > top_rank:
                        keystack.insert(0, word)
                        top_rank = rule.precedence
                    else:
                        keystack.append(word)
                if rule.substitute:
                    words[i] = rule.substitute
            i += 1
        trace("clause: " + join(words) + "   keystack: " + " ".join(keystack))

        if not keystack and self.limit == 4 and self.memories:
            trace("recall memory")
            return self.memories.pop(0)

        while keystack:
            keyword = keystack.pop(0)
            rule = self.script.rules.get(keyword)
            if rule is None:
                trace(f"unknown keyword {keyword}")
                if self.use_nomatch_msgs:
                    return self.nomatch()
                break

            self._create_memory(keyword, words)

            action, link, words = self._transform(rule, words)
            if action == "complete":
                return join(words)
            if action == "inapplicable":
                trace("no decomposition matches (script error?)")
                if self.use_nomatch_msgs:
                    return self.nomatch()
                break
            if action == "link":
                keystack.insert(0, link)
            elif not keystack:  # NEWKEY with nothing left to try
                if not self.on_newkey_fail_use_none and self.use_nomatch_msgs:
                    return self.nomatch()
                break

        # the NONE rule never fails [CACM p. 41]
        _, _, words = self._transform(self.script.none, words, "NONE")
        return join(words)

    # ----------------------------------------------------------------------

    def _create_memory(self, keyword: str, words: list[str]) -> None:
        memory = self.script.memory
        if keyword != memory.keyword:
            return
        index = slip_hash(last_chunk_as_bcd(words[-1]), 2)
        decomposition, reassembly = memory.transformations[index]
        components = match(self.tags, decomposition, words)
        if components is None:
            self.trace(f"memory {index + 1} does not match")
            return
        new = join(reassemble(reassembly, components))
        self.trace(f"new memory ({index + 1}): {new}")
        self.memories.append(new)

    def _transform(self, rule: KeywordRule, words: list[str], name: str = ""):
        """Apply rule to words; return (action, link keyword, words)."""
        name = name or rule.keyword
        for t_index, t in enumerate(rule.transformations):
            components = match(self.tags, t.decomposition, words)
            if components is not None:
                break
        else:
            if rule.link:
                self.trace(f"{name}: no decomposition matches, go to {rule.link}")
                return "link", rule.link, words
            return "inapplicable", "", words

        key = (name, t_index)
        r_index = self._next.get(key, 0)
        self._next[key] = (r_index + 1) % len(t.reassemblies)
        r = t.reassemblies[r_index]
        self.trace(f"{name}: ({join(t.decomposition)}) -> {r.kind} {join(r.words)} {r.keyword}")

        if r.kind == "newkey":
            return "newkey", "", words
        if r.kind == "link":
            return "link", r.keyword, words
        if r.kind == "pre":
            return "link", r.keyword, reassemble(r.words, components)
        return "complete", "", reassemble(r.words, components)
