"""Turning modern Unicode text into the words ELIZA works with.

ELIZA expected only the 7094 BCD character set: upper case letters,
digits and a little punctuation. Modern users type lower case, curly
quotes, accented letters or other scripts. These functions reinterpret
such text in the way eliza.cpp does, so that both programs produce the
same conversations, and add two language-neutral options:

- NFC normalisation, so "é" typed as e + combining accent equals "é";
- optional accent folding ("RÊVE" == "REVE"), useful when users cannot
  type accents; it must then be applied to the script as well.
"""

from __future__ import annotations

import unicodedata

# characters reinterpreted before upper-casing (same choices as eliza.cpp)
_REPLACE = {
    "’": "'",   # right single quotation mark, as in I’m
    "‘": " ", "`": " ", '"': " ", "«": " ", "»": " ",
    "‚": " ", "‛": " ", "“": " ", "”": " ",
    "„": " ", "‟": " ", "‹": " ", "›": " ",
    "!": ".", "?": ".",
    "¡": " ", "¿": " ",
    ":": ",", ";": ",", "–": ",", "—": ",",
    "ß": "SS",
    "ﬀ": "FF", "ﬁ": "FI", "ﬂ": "FL",
    "ﬃ": "FFI", "ﬄ": "FFL", "ﬅ": "ST", "ﬆ": "ST",
}
# Unicode spaces, notably the (narrow) no-break spaces of French typography
# inside « » and before ; : ! ? -- an addition: eliza.cpp keeps them inside
# words, so "« NON »" would never match NON
_REPLACE.update(dict.fromkeys(
    "            "
    "   　\t", " "))


def eliza_uppercase(text: str) -> str:
    """Return text upper-cased, with quotes and punctuation reinterpreted.

    e.g. "Hello! How are you?" -> "HELLO. HOW ARE YOU."
         "I’m depressed"       -> "I'M DEPRESSED"
    """
    out = []
    for ch in unicodedata.normalize("NFC", text):
        rep = _REPLACE.get(ch)
        if rep is None:
            up = ch.upper()
            # keep one character per character where Unicode would expand
            # (e.g. "ŉ" -> "ʼN"); ELIZA words are compared verbatim anyway
            out.append(up if len(up) == 1 else ch)
        else:
            out.append(rep)
    return "".join(out)


def fold_accents(text: str) -> str:
    """Remove combining marks: "PEUT-ÊTRE" -> "PEUT-ETRE", "ÇA" -> "CA".

    Letters that are not decomposable (Æ, Ø, Œ, ...) are kept.
    """
    decomposed = unicodedata.normalize("NFD", text)
    kept = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", kept)


def split(text: str) -> list[str]:
    """Split on spaces only (not tabs), as eliza.cpp does."""
    return [w for w in text.split(" ") if w]


def join(words) -> str:
    """Join words with single spaces, skipping empty words."""
    return " ".join(w for w in words if w)


def split_user_input(text: str, punctuation: str) -> list[str]:
    """Split text into words; each punctuation character is a word on its own.

    e.g. split_user_input("ONE   ABUTMENT, BUT THREE.", ",.")
           -> ["ONE", "ABUTMENT", ",", "BUT", "THREE", "."]
    """
    result: list[str] = []
    word: list[str] = []
    for ch in text:
        if ch == " " or ch in punctuation:
            if word:
                result.append("".join(word))
                word = []
            if ch != " ":
                result.append(ch)
        else:
            word.append(ch)
    if word:
        result.append("".join(word))
    return result


def to_int(s: str) -> int:
    """Return the value of an all-digit string, else -1 ("2" -> 2, "TWO" -> -1)."""
    return int(s) if s and s.isascii() and s.isdigit() else -1
