"""Decomposition (YMATCH) and reassembly (ASSMBL).

A decomposition pattern is a list of terms:

    0               any number of words, possibly none
    N (N > 0)       exactly N words
    WORD            that word
    (*A B C)        one word among A, B, C
    (/TAG1 TAG2)    one word carrying one of the DLIST tags

The matcher follows the structure of the SLIP YMATCH code rather than a
general backtracking search: the pattern is cut into segments, each
starting at a 0 wildcard, and a 0 that is not the last one takes the
fewest words possible. This is the default matcher of eliza.cpp.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .text import join, split, to_int

# a DLIST tag enabling the 6-character comparison quirk found in the
# Quarton, McGuire and Lorch pilot study conversations (see eliza.cpp)
SIX_CHAR_MATCHING_TAG = "USE_SIX_CHAR_MATCHING_BEHAVIOR"

TagMap = Mapping[str, Sequence[str]]


def inlist(word: str, wordlist: str, tags: TagMap) -> bool:
    """Is word in a "(*A B C)" choice or does it carry a "(/TAG ...)" tag?"""
    s = wordlist[:-1] if wordlist.endswith(")") else wordlist
    if s.startswith("("):
        s = s[1:]
    s = s.lstrip(" ")
    if s.startswith("*"):
        choices = split(s[1:])
        if list(tags.get(SIX_CHAR_MATCHING_TAG, ())) == [SIX_CHAR_MATCHING_TAG]:
            # the first SLIP cell of word compared with every cell of each
            # choice (WONDER matches WONDERFUL); cells are 6 characters, here
            # 6 UTF-8 bytes as in eliza.cpp
            word6 = word.encode("utf-8", "surrogatepass")[:6]
            for choice in choices:
                data = choice.encode("utf-8", "surrogatepass")
                if any(data[i:i + 6] == word6 for i in range(0, len(data), 6)):
                    return True
            return False
        return word in choices
    if s.startswith("/"):
        return any(word in tags.get(tag, ()) for tag in split(s[1:]))
    return False


def _match_segment(tags, pattern, words, p_begin, p_end, w_begin, fixed_len, result):
    """Match pattern[p_begin:p_end] against words from w_begin.

    The segment holds at most one 0 wildcard, as its first term. Return
    the index just after the matched words, or None.
    """
    if len(words) - w_begin < fixed_len:
        return None
    has_wildcard = to_int(pattern[p_begin]) == 0
    wildcard_len = wildcard_end = 0
    if has_wildcard:
        if p_end == len(pattern):
            # last segment: the wildcard takes whatever the rest leaves
            wildcard_len = wildcard_end = len(words) - w_begin - fixed_len
        else:
            # inner segment: the wildcard takes as few words as possible
            wildcard_end = len(words) - w_begin - fixed_len

    while True:
        p = p_begin + has_wildcard
        w = w_begin + wildcard_len
        while p < p_end:
            term = pattern[p]
            n = to_int(term)
            if n > 0:
                result[p] = join(words[w:w + n])
                w += n
            elif term.startswith("("):
                if not inlist(words[w], term, tags):
                    break
                result[p] = words[w]
                w += 1
            elif term == words[w]:
                result[p] = words[w]
                w += 1
            else:
                break
            p += 1
        if p == p_end:
            if has_wildcard:
                result[p_begin] = join(words[w_begin:w_begin + wildcard_len])
            return w
        if wildcard_len == wildcard_end:
            return None
        wildcard_len += 1


def match(tags: TagMap, pattern: Sequence[str], words: Sequence[str]) -> list[str] | None:
    """Return the matched components, one per pattern term, or None.

    e.g. match({}, ["0", "YOU", "(*WANT NEED)", "0"], ["YOU", "NEED", "NICE", "FOOD"])
           -> ["", "YOU", "NEED", "NICE FOOD"]
    """
    result = [""] * len(pattern)
    w = 0
    seg_end = 0
    while seg_end < len(pattern):
        seg_begin = seg_end
        fixed_len = 0
        while seg_end < len(pattern):
            n = to_int(pattern[seg_end])
            if n == 0:
                if seg_end > seg_begin:
                    break  # a 0 that is not first starts the next segment
            elif n > 0:
                fixed_len += n
            else:
                fixed_len += 1
            seg_end += 1
        w = _match_segment(tags, pattern, words, seg_begin, seg_end, w, fixed_len, result)
        if w is None:
            return None
    if w < len(words):
        return None
    return result


def reassemble(rule: Sequence[str], components: Sequence[str]) -> list[str]:
    """Build a reply: numbers are replaced by the numbered components.

    e.g. reassemble(["ARE", "YOU", "1"], ["MAD", "ABOUT YOU"]) -> ["ARE", "YOU", "MAD"]
    An index out of range gives "HMMM" (scripts are checked when read).
    """
    out: list[str] = []
    for term in rule:
        n = to_int(term)
        if n < 0:
            out.append(term)
        elif n == 0 or n > len(components):
            out.append("HMMM")
        else:
            out.extend(split(components[n - 1]))
    return out
