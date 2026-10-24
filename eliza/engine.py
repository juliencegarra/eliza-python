"""The ELIZA algorithm, in two historical versions.

version="1966" (default) follows the 1966 CACM description as
reconstructed by Anthony Hay (eliza.cpp), including what the MAD-SLIP
listing of March 1965 revealed:

- BUT is a delimiter, like the comma and the period;
- "a certain counting mechanism" is LIMIT, cycling 1, 2, 3, 4: a memory
  is recalled only when LIMIT is 4 and the input has no keyword;
- the MEMORY transformation is chosen by HASH of the last input cell,
  not at random, so conversations are reproducible;
- a keyword whose decompositions all fail gives one of four built-in
  messages, chosen by LIMIT.

version="1965" is the program of the recovered listing itself (validated
against the original code running on an emulated IBM 7094):

- no keyword stack: only the keyword of highest rank is used, the first
  one among equals; there is no NEWKEY and no PRE;
- a link (=KEYWORD) is followed only in place of a transformation; as a
  reassembly rule it is printed as it stands: "= DIT";
- words are compared on their first SLIP cell (6 characters): a keyword
  sharing its first 6 characters with an earlier one is never found;
- the (*A B C) choices compare 6-character cells (see match.py);
- punctuation is printed apart: "REALLY , EVERYONE".

Both versions can be taught during a conversation, as the 1965 code could:
"+" opens the script editor (TYPE, SUBST, APPEND, ADD, RANK, DISPLA, START)
and "* KEYWORD ..." adds a keyword rule; script_text() writes the revised
script, as the original did when the conversation ended.

Unlike eliza.cpp the per-rule state (which reassembly comes next) and the
script are copied into each Eliza object, so a Script can serve several
conversations and teaching one does not change the others.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field

from .hollerith import cell_as_bcd, last_chunk_as_bcd, slip_hash
from .languages import ENGLISH, Language
from .match import SIX_CHAR_MATCHING_TAG, match, reassemble
from .script import (KeywordRule, Reassembly, Script, ScriptError, Transformation,
                     memory_text, parse_items, parse_rule, reassembly_text, rule_text, to_text)
from .text import eliza_uppercase, fold_accents, join, split_user_input

# punctuation that can be a delimiter: the 7094 BCD set, less the space
_BCD_PUNCTUATION = "='+.)-$*/,("

VERSIONS = ("1965", "1966")


@dataclass
class Trace:
    """What ELIZA did to produce the last response.

    lines is a readable account (the * command of the CLI); steps holds the
    same information as data, for the step-by-step display of the web page.
    """
    lines: list[str] = field(default_factory=list)
    steps: dict = field(default_factory=dict)

    def __call__(self, line: str) -> None:
        self.lines.append(line)

    def text(self) -> str:
        return "\n".join(" | " + line for line in self.lines)


def _cell(word: str) -> bytes:
    """The first SLIP cell of a word: its first 6 characters (UTF-8 bytes)."""
    return word.encode("utf-8", "surrogatepass")[:6]


def _bucket(word: str) -> int:
    """The KEY table entry of a keyword in the 1965 code: HASH of its first cell."""
    return slip_hash(cell_as_bcd(_cell(word)), 5)


def _flat(items) -> tuple[str, ...]:
    """["0", ["*", "A", "B"]] -> ("0", "(* A B)")."""
    return tuple(i if isinstance(i, str) else "(" + " ".join(_flat(i)) + ")" for i in items)


def _reassembly(items) -> Reassembly:
    words = _flat(items)
    if words == ("NEWKEY",):
        return Reassembly("newkey")
    if len(words) == 2 and words[0] == "=":
        return Reassembly("link", keyword=words[1])
    if len(items) == 3 and items[0] == "PRE" and not isinstance(items[1], str) \
            and not isinstance(items[2], str) and len(items[2]) == 2 and items[2][0] == "=":
        return Reassembly("pre", _flat(items[1]), items[2][1])
    return Reassembly("words", words)


def _items_of(r: Reassembly) -> tuple[str, ...]:
    if r.kind == "link":
        return ("=", r.keyword)
    if r.kind == "newkey":
        return ("NEWKEY",)
    if r.kind == "pre":
        return ("PRE", "(" + " ".join(r.words) + ")", f"(= {r.keyword})")
    return r.words


class Eliza:
    max_links = 20_000  # links followed for one input, then give up (script loop)

    def __init__(
        self,
        script: Script,
        language: Language = ENGLISH,
        *,
        version: str = "1966",
        use_nomatch_msgs: bool = True,
        on_newkey_fail_use_none: bool = True,
        fold_input_accents: bool = False,
        teaching: bool = True,
    ):
        """
        language                 delimiters and built-in messages (see languages.py)
        version                  "1966" (CACM paper) or "1965" (recovered listing)
        use_nomatch_msgs         True: script errors give the built-in messages, as
                                 Weizenbaum's code did; False: use the NONE rule
        on_newkey_fail_use_none  NEWKEY with an empty keystack uses NONE [CACM p. 41]
                                 (the Quarton study suggests a built-in message)
        fold_input_accents       remove accents from the input; only useful with a
                                 script whose words were folded the same way
        teaching                 "+" and "*" edit the script, as in the 1965 code
        """
        if version not in VERSIONS:
            raise ValueError(f"unknown version '{version}'; known: {', '.join(VERSIONS)}")
        self.script = dataclasses.replace(script, rules=dict(script.rules),
                                          metadata=dict(script.metadata))
        self.language = language
        self.version = version
        self.use_nomatch_msgs = use_nomatch_msgs
        self.on_newkey_fail_use_none = on_newkey_fail_use_none
        self.fold_input_accents = fold_input_accents
        self.teaching = teaching
        self.delimiters = set(language.delimiters)
        self.punctuation = "".join(
            d for d in language.delimiters if len(d) == 1 and d in _BCD_PUNCTUATION)
        self.limit = 1          # Weizenbaum's LIMIT
        self.memories: list[str] = []
        self._next: dict[tuple[str, int], int] = {}  # next reassembly per decomposition
        self.editing = False    # in the script editor opened by "+"
        self.modified = False   # the script was taught something
        self.trace = Trace()
        self._script_changed()

    def _script_changed(self) -> None:
        self.tags = self.script.tags()
        if self.version == "1965":
            self.tags[SIX_CHAR_MATCHING_TAG] = [SIX_CHAR_MATCHING_TAG]
            self._by_cell: dict[bytes, KeywordRule] = {}
            for rule in self.script.rules.values():
                self._by_cell.setdefault(_cell(rule.keyword), rule)

    # ----------------------------------------------------------------------

    def hello(self) -> str:
        return self._output(join(self.script.hello))

    def nomatch(self) -> str:
        return self.language.nomatch_messages[self.limit - 1]

    def words(self, text: str) -> list[str]:
        """The input as ELIZA sees it: "Hello, world!" -> HELLO , WORLD ."""
        text = eliza_uppercase(text)
        if self.fold_input_accents:
            text = fold_accents(text)
        return self.language.split_elisions(split_user_input(text, self.punctuation))

    def script_text(self) -> str:
        """The script, with what was taught, as a script file."""
        return to_text(self.script)

    def _output(self, text: str) -> str:
        text = self.language.join_elisions(text)
        if self.version == "1965":
            # TXTPRT prints each cell apart, and TREAD put "," and "." in cells of their own
            text = " ".join(re.sub(r"([,.])", r" \1 ", text).split())
        return text

    # ----------------------------------------------------------------------

    def response(self, text: str) -> str:
        self.trace = Trace()
        command = text.split(None, 1)
        if self.teaching and (self.editing or (command and command[0] in ("+", "*"))):
            reply = self._teach(text)
            self.trace.steps.update(source="command", reply=reply,
                                    memories=[self._output(m) for m in self.memories])
            return reply
        reply = self._output(self._response(text))
        self.trace.steps.update(reply=reply, memories=[self._output(m) for m in self.memories])
        return reply

    def _response(self, text: str) -> str:
        trace = self.trace
        steps = trace.steps
        words = self.words(text)
        trace("input: " + join(words))
        steps.update(version=self.version, input=list(words), discarded=[], keywords=[],
                     rules=[], memory_new=None)

        self.limit = self.limit % 4 + 1
        trace(f"LIMIT: {self.limit} ({self.nomatch()})")
        steps["limit"] = self.limit

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
                    steps["discarded"].append(join(words[:i + 1]))
                    del words[:i + 1]
                    i = 0
                    continue
                trace("cut: " + join(words[i:]))
                steps["cut"] = join(words[i:])
                del words[i:]
                break
            rule = self._keyword(word)
            if rule is not None:
                steps["keywords"].append(dict(word=word, precedence=rule.precedence,
                                              substitute=rule.substitute,
                                              transformation=rule.has_transformation))
                if rule.has_transformation:
                    if self.version == "1965":
                        # 1965: the first keyword, or one of strictly higher rank
                        if (not keystack and rule.precedence == 0) or rule.precedence > top_rank:
                            keystack[:] = [word]
                            top_rank = max(top_rank, rule.precedence)
                    elif rule.precedence > top_rank:
                        keystack.insert(0, word)
                        top_rank = rule.precedence
                    else:
                        keystack.append(word)
                if rule.substitute:
                    words[i] = rule.substitute
            i += 1
        trace("clause: " + join(words) + "   keystack: " + " ".join(keystack))
        steps.update(clause=join(words), keystack=list(keystack))

        if not keystack and self.limit == 4 and self.memories:
            trace("recall memory")
            steps["source"] = "memory"
            return self.memories.pop(0)

        if self.version == "1965":
            reply = self._apply_1965(keystack, words)
            if reply is not None:
                return reply
        else:
            links = 0
            while keystack:
                keyword = keystack.pop(0)
                rule = self.script.rules.get(keyword)
                if rule is None:
                    trace(f"unknown keyword {keyword}")
                    if self.use_nomatch_msgs:
                        steps["source"] = "nomatch"
                        return self.nomatch()
                    break

                self._create_memory(keyword, words)

                action, link, words = self._transform(rule, words)
                if action == "complete":
                    steps["source"] = "rule"
                    return join(words)
                if action == "inapplicable":
                    trace("no decomposition matches (script error?)")
                    if self.use_nomatch_msgs:
                        steps["source"] = "nomatch"
                        return self.nomatch()
                    break
                if action == "link":
                    links += 1
                    if links > self.max_links:
                        trace(f"more than {self.max_links} links: the script loops")
                        steps["source"] = "nomatch"
                        return self.nomatch()
                    keystack.insert(0, link)
                elif not keystack:  # NEWKEY with nothing left to try
                    if not self.on_newkey_fail_use_none and self.use_nomatch_msgs:
                        steps["source"] = "nomatch"
                        return self.nomatch()
                    break

        # the NONE rule never fails [CACM p. 41]
        steps["source"] = "none"
        _, _, words = self._transform(self.script.none, words, "NONE")
        return join(words)

    def _keyword(self, word: str) -> KeywordRule | None:
        if self.version == "1965":
            # KEY is searched for the first cell, then TESTS compares whole words
            rule = self._by_cell.get(_cell(word))
            return rule if rule is not None and rule.keyword == word else None
        return self.script.rules.get(word)

    def _apply_1965(self, keystack: list[str], words: list[str]) -> str | None:
        """MATCH and HIT of the 1965 code; None means use the NONE rule."""
        if not keystack:
            return None
        rule = self.script.rules[keystack[0]]
        if _cell(rule.keyword) == _cell(self.script.memory.keyword):
            self._create_memory(self.script.memory.keyword, words)
        for _ in range(self.max_links):
            action, link, out = self._transform(rule, words)
            if action == "complete":
                self.trace.steps["source"] = "rule"
                return join(out)
            if action != "link":
                break
            # a link in place of a transformation: KEY searched on the first cell only
            rule = self._by_cell.get(_cell(link))
            if rule is None:
                break
        self.trace("no decomposition matches (script error?)")
        self.trace.steps["source"] = "nomatch"
        return self.nomatch()

    # ----------------------------------------------------------------------

    def _create_memory(self, keyword: str, words: list[str]) -> None:
        memory = self.script.memory
        if keyword != memory.keyword or not words:
            return
        index = slip_hash(last_chunk_as_bcd(words[-1]), 2)
        decomposition, reassembly = memory.transformations[index]
        components = match(self.tags, decomposition, words)
        if components is None:
            self.trace(f"memory {index + 1} does not match")
            return
        new = join(reassemble(reassembly, components))
        self.trace(f"new memory ({index + 1}): {new}")
        self.trace.steps["memory_new"] = dict(text=self._output(new), index=index + 1,
                                              last_word=words[-1], rule=join(decomposition))
        self.memories.append(new)

    def _transform(self, rule: KeywordRule, words: list[str], name: str = ""):
        """Apply rule to words; return (action, link keyword, words)."""
        name = name or rule.keyword
        step = dict(keyword=name, words=join(words), decomposition=None, components=None,
                    reassembly=None, action=None)
        self.trace.steps.setdefault("rules", []).append(step)
        for t_index, t in enumerate(rule.transformations):
            components = match(self.tags, t.decomposition, words)
            if components is not None:
                break
        else:
            if rule.link:
                self.trace(f"{name}: no decomposition matches, go to {rule.link}")
                step.update(action="link", link=rule.link)
                return "link", rule.link, words
            step["action"] = "inapplicable"
            return "inapplicable", "", words

        key = (name, t_index)
        r_index = self._next.get(key, 0)
        self._next[key] = (r_index + 1) % len(t.reassemblies)
        r = t.reassemblies[r_index]
        self.trace(f"{name}: ({join(t.decomposition)}) -> {r.kind} {join(r.words)} {r.keyword}")
        step.update(decomposition=join(t.decomposition), components=list(components),
                    reassembly=reassembly_text(r), choice=f"{r_index + 1}/{len(t.reassemblies)}")

        if self.version == "1965" and r.kind != "words":
            # neither NEWKEY, PRE nor reassembly links exist in 1965: ASSMBL prints them
            step["action"] = "complete"
            return "complete", "", list(_items_of(r) if r.kind != "pre" else
                                        ("PRE", *r.words, "=", r.keyword))
        if r.kind == "newkey":
            step["action"] = "newkey"
            return "newkey", "", words
        if r.kind == "link":
            step.update(action="link", link=r.keyword)
            return "link", r.keyword, words
        if r.kind == "pre":
            out = reassemble(r.words, components)
            step.update(action="pre", link=r.keyword, output=join(out))
            return "link", r.keyword, out
        out = reassemble(r.words, components)
        step.update(action="complete", output=join(out))
        return "complete", "", out

    # ----------------------------------------------------------------------
    # teaching: "+" (CHANGE) and "*" (NEWLST) of the 1965 code

    def _teach(self, text: str) -> str:
        instruct, not_recognized, not_found, memory_list = self.language.editor_messages
        if not self.editing:
            self.limit = self.limit % 4 + 1  # these lines go through the main loop
            if text.split(None, 1)[0] == "+":
                self.editing = True
                return instruct
            try:
                rule = parse_rule("(" + text.strip()[1:] + ")", self.script.rules)
            except ScriptError as error:
                return str(error).upper()
            self._set_rule(rule)
            self.trace(f"new rule {rule.keyword}")
            return ""
        try:
            items = parse_items(text)
        except ScriptError:
            return not_recognized + "\n" + instruct
        command = items[0] if items and isinstance(items[0], str) else ""
        if command == "START":
            self.editing = False
            return ""
        if command == "DISPLA":
            return self._display(memory_list) + "\n" + instruct
        if command not in ("TYPE", "SUBST", "APPEND", "ADD", "RANK") or len(items) < 2 \
                or not isinstance(items[1], str):
            return not_recognized + "\n" + instruct
        rule = self._rule_named(items[1])
        if rule is None:
            return not_found + "\n" + instruct
        try:
            output = self._edit(command, rule, items[2:])
        except (ValueError, IndexError, TypeError):
            output = not_recognized
        if output is None:
            output = not_found
        return (output + "\n" if output else "") + instruct

    def _rule_named(self, keyword: str) -> KeywordRule | None:
        if keyword == "NONE":
            return self.script.none
        if self.version == "1965":
            return self._by_cell.get(_cell(keyword))
        return self.script.rules.get(keyword)

    def _set_rule(self, rule: KeywordRule) -> None:
        if rule is self.script.none or rule.keyword == "NONE":
            self.script.none = rule
        else:
            self.script.rules[rule.keyword] = rule
        self.modified = True
        self._script_changed()

    def _edit(self, command: str, rule: KeywordRule, args: list) -> str | None:
        """One editor command; return its output, or None for "list not found"."""
        name = "NONE" if rule is self.script.none else rule.keyword
        if command == "TYPE":
            return rule_text(rule, name)
        if command == "RANK":
            new = dataclasses.replace(rule, precedence=int(args[0]))
        elif command == "ADD":
            if not isinstance(args[0], list) or not args[0] or isinstance(args[0][0], str):
                raise ValueError("expected ((decomposition) (reassembly) ...)")
            decomposition, *reassemblies = args[0]
            t = Transformation(_flat(decomposition), tuple(_reassembly(r) for r in reassemblies))
            if not t.reassemblies:
                raise ValueError("no reassembly")
            new = dataclasses.replace(rule, transformations=rule.transformations + (t,))
        else:  # SUBST or APPEND: (old) (new); old may be the start of the rule it names
            if len(args) != 2 or isinstance(args[0], str) or isinstance(args[1], str):
                raise ValueError("expected (old) (new)")
            old, replacement = _flat(args[0]), args[1]
            transformations = list(rule.transformations)
            for i, t in enumerate(transformations):
                items = [t.decomposition] + [_items_of(r) for r in t.reassemblies]
                found = next((j for j, item in enumerate(items) if item[:len(old)] == old), None)
                if found is None:
                    continue
                if command == "APPEND":
                    t = dataclasses.replace(
                        t, reassemblies=t.reassemblies + (_reassembly(replacement),))
                elif found == 0:
                    t = dataclasses.replace(t, decomposition=_flat(replacement))
                else:
                    reassemblies = list(t.reassemblies)
                    reassemblies[found - 1] = _reassembly(replacement)
                    t = dataclasses.replace(t, reassemblies=tuple(reassemblies))
                transformations[i] = t
                break
            else:
                return None
            new = dataclasses.replace(rule, transformations=tuple(transformations))
        self._set_rule(new)
        return ""

    def _display(self, memory_list: str) -> str:
        """DISPLA: every keyword rule with its KEY table entry, then the memory."""
        parts = []
        for rule in sorted(self.script.rules.values(), key=lambda r: _bucket(r.keyword)):
            parts.append(f"*\n{rule_text(rule)}\n{_bucket(rule.keyword):3d}")
        parts.append(f"*\n{rule_text(self.script.none, 'NONE')}\n 32")
        parts.append(memory_list + "\n" + memory_text(self.script.memory))
        return "\n".join(parts)
