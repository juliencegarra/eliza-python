"""Unit tests, mostly translated from the DEF_TEST_FUNC tests of eliza.cpp (CC0)."""

from __future__ import annotations

import re

import pytest

from eliza.hollerith import last_chunk_as_bcd, slip_hash
from eliza.match import SIX_CHAR_MATCHING_TAG, inlist, match, reassemble
from eliza.text import eliza_uppercase, fold_accents, join, split, split_user_input, to_int


def test_hash_known_values():
    # "ALWAYS" -> 14 [CACM 1966 p. 38]; "HERE" -> 3 (the published memory)
    assert slip_hash(0o214366217062, 7) == 14
    assert slip_hash(0o302551256060, 2) == 3
    # deduced from the March 1965 conversations
    assert slip_hash(0o423124626060, 2) == 1
    assert slip_hash(0o633144256060, 2) == 0
    # made up, checked by hand in eliza.cpp
    assert slip_hash(0o777777777777, 7) == 0x70
    assert slip_hash(0o777777777777, 15) == 0x7F00
    assert slip_hash(0x555555555, 15) == 0x46E3
    assert slip_hash(0xF0F0F0F0F, 15) == 0x7788
    assert slip_hash(0, 7) == 0


# bucket of each keyword of TAPE 100, read from the original code running
# on CTSS (Rupert Lane's emulator, CHANGE / DISPLA commands)
TAPE_100_BUCKETS = {
    "NOONE": 0, "WIFE": 1, "I": 2, "CAN": 2, "BECAUSE": 3, "IF": 5, "CHILDREN": 5,
    "HOW": 6, "YES": 6, "ALWAYS": 7, "MY": 8, "YOU'RE": 11, "ARE": 12, "EVERYONE": 12,
    "MAYBE": 13, "YOU": 13, "AM": 16, "YOUR": 17, "PERHAPS": 18, "MYSELF": 19,
    "BROTHER": 21, "WHAT": 21, "MOTHER": 22, "SISTER": 22, "NO": 24, "I'M": 25,
    "WHY": 27, "NOBODY": 27, "FATHER": 28, "WHEN": 29, "WAS": 29, "ME": 29,
    "YOURSELF": 30, "WERE": 31, "EVERYBODY": 31,
}


@pytest.mark.parametrize("word,bucket", TAPE_100_BUCKETS.items())
def test_hash_tape_100_buckets(word, bucket):
    # the KEY table is indexed by the hash of the FIRST cell of the keyword
    first_cell = word[:6]
    assert slip_hash(last_chunk_as_bcd(first_cell), 5) == bucket


@pytest.mark.parametrize("word,value", [
    ("PURPOSE", 1), ("DEVONSHIRE", 0), ("PREDICAMENT", 3),
    ("EXECUTIONERS", 3), ("GLOUCESTERSHIRE", 2),
])
def test_memory_choice_on_ctss(word, value):
    assert slip_hash(last_chunk_as_bcd(word), 2) == value


def test_last_chunk_as_bcd():
    assert last_chunk_as_bcd("") == 0o606060606060
    assert last_chunk_as_bcd("X") == 0o676060606060
    assert last_chunk_as_bcd("HERE") == 0o302551256060
    assert last_chunk_as_bcd("ALWAYS") == 0o214366217062
    assert last_chunk_as_bcd("INVENTED") == 0o252460606060
    assert last_chunk_as_bcd("123456ABCDEF") == 0o212223242526
    assert last_chunk_as_bcd("Ç") == 0o030760606060  # Ç, as UTF-8 bytes


def test_uppercase():
    assert eliza_uppercase("Hello! How are you?") == "HELLO. HOW ARE YOU."
    assert eliza_uppercase("I’m depressed") == "I'M DEPRESSED"
    assert eliza_uppercase("I'm «depressed»") == "I'M  DEPRESSED "
    assert eliza_uppercase("à â ç é è ê ë î ï ô ù û ü ÿ æ œ eﬃgy Straße") == \
        "À Â Ç É È Ê Ë Î Ï Ô Ù Û Ü Ÿ Æ Œ EFFIGY STRASSE"
    assert eliza_uppercase("Сайфи Кудаш") == "САЙФИ КУДАШ"
    assert eliza_uppercase("¡pónk!") == " PÓNK."
    assert eliza_uppercase("–I'm not entirely certain—maybe") == \
        ",I'M NOT ENTIRELY CERTAIN,MAYBE"
    all_bcd = "0123456789='+ABCDEFGHI.)-JKLMNOPQR$* /STUVWXYZ,("
    assert eliza_uppercase(all_bcd) == all_bcd


def test_french_typography():
    # straight and curly apostrophes are the same; quotes and (narrow)
    # no-break spaces vanish, so the words inside still match
    assert eliza_uppercase("J'ai") == eliza_uppercase("J’ai") == "J'AI"
    words = split_user_input(eliza_uppercase("J’ai dit « non » ; vraiment !"), ",.")
    assert words == ["J'AI", "DIT", "NON", ",", "VRAIMENT", "."]
    assert split_user_input(eliza_uppercase('J\'ai dit "non"'), ",.") == ["J'AI", "DIT", "NON"]


def test_unicode_normalisation_and_folding():
    decomposed = "rêve"  # e + combining circumflex
    assert eliza_uppercase(decomposed) == "RÊVE"
    assert fold_accents("PEUT-ÊTRE ÇA") == "PEUT-ETRE CA"
    assert fold_accents("ŒUVRE") == "ŒUVRE"


def test_split_join_to_int():
    assert split(" one two, three,, don't. ") == ["one", "two,", "three,,", "don't."]
    assert join(["one", "two", "", "3"]) == "one two 3"
    assert split_user_input("ONE   TWO, THREE,, DON'T.", ",.") == \
        ["ONE", "TWO", ",", "THREE", ",", ",", "DON'T", "."]
    assert split_user_input("ONE   ABUTMENT, BUT THREE.", ".") == ["ONE", "ABUTMENT,", "BUT", "THREE", "."]
    assert [to_int(s) for s in ("0", "1", "2023", "-42", "int")] == [0, 1, 2023, -1, -1]


TAGS = {"FAMILY": ["MOTHER", "FATHER", "SISTER", "BROTHER", "WIFE", "CHILDREN"],
        "NOUN": ["MOTHER", "FATHER", "FISH", "FOUL"]}


def test_inlist():
    assert inlist("MOTHER", "(/FAMILY)", TAGS)
    assert inlist("BROTHER", "( / FAMILY )", TAGS)
    assert not inlist("FISH", "(/FAMILY)", TAGS)
    assert inlist("FOUL", "(/ NOUN  FAMILY )", TAGS)
    assert not inlist("MOTHER", "(/NONEXISTANTTAG)", TAGS)
    assert inlist("SAD", "(*SAD HAPPY DEPRESSED)", TAGS)
    assert inlist("DEPRESSED", "( * SAD HAPPY DEPRESSED )", TAGS)
    assert not inlist("DRUNK", "( * SAD HAPPY DEPRESSED )", TAGS)
    assert not inlist("WONDER", "(*HAPPY ELATED EXCITED GOOD WONDERFUL)", TAGS)


def test_inlist_six_char_quirk():
    tags = dict(TAGS, **{SIX_CHAR_MATCHING_TAG: [SIX_CHAR_MATCHING_TAG]})
    for word in ("WONDER", "FUL", "D"):
        assert inlist(word, "(*HAPPY ELATED EXCITED GOOD WONDERFUL)", tags)
    assert not inlist("DRUNK", "(*SAD HAPPY DEPRESSED)", tags)


@pytest.mark.parametrize("pattern,words,expected", [
    ("0 YOU (*WANT NEED) 0", "YOU NEED NICE FOOD", ["", "YOU", "NEED", "NICE FOOD"]),
    ("0 0 YOU (*WANT NEED) 0", "YOU WANT NICE FOOD", ["", "", "YOU", "WANT", "NICE FOOD"]),
    ("1 (*WANT NEED) 0", "YOU WANT NICE FOOD", ["YOU", "WANT", "NICE FOOD"]),
    ("1 (*WANT NEED) 1", "YOU WANT NICE FOOD", None),
    ("1 (*WANT NEED) 2", "YOU WANT NICE FOOD", ["YOU", "WANT", "NICE FOOD"]),
    ("0 YOUR 0 (/FAMILY) 0", "YOUR MOTHER", ["", "YOUR", "", "MOTHER", ""]),
    ("0 YOUR 0 (/FAMILY) 0", "MY MOTHER", None),
    ("0 YOU ARE 0 I 0", "I THINK YOU ARE AFRAID OF I", ["I THINK", "YOU", "ARE", "AFRAID OF", "I", ""]),
    ("0", "", [""]),
    ("0 0", "A B", ["", "A B"]),
    ("A 1 0", "A HILL OF BEANS", ["A", "HILL", "OF BEANS"]),
    # the inner 0 is not greedy: the first YOU after MARY is used
    ("0 YOU 0 YOU 0", "MARY YOU HAD YOU A YOU LAMB", ["MARY", "YOU", "HAD", "YOU", "A YOU LAMB"]),
])
def test_match(pattern, words, expected):
    terms = re.findall(r"\([^)]*\)|\S+", pattern)
    assert match(TAGS, terms, words.split()) == expected


def test_reassemble():
    parts = ["MARY", "HAD A", "LITTLE LAMB", "ITS", "PROBABILITY", "WAS ZERO"]
    assert reassemble(["DID", "1", "HAVE", "A", "3"], parts) == ["DID", "MARY", "HAVE", "A", "LITTLE", "LAMB"]
    assert reassemble(["1", "-1", "1"], parts) == ["MARY", "-1", "MARY"]
    assert reassemble(["1", "0", "1"], parts) == ["MARY", "HMMM", "MARY"]
    assert reassemble(["1", "7", "1"], parts) == ["MARY", "HMMM", "MARY"]
