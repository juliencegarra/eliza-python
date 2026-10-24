"""Language-dependent parts of the program (not of the script).

Almost everything language-specific in ELIZA lives in the script: the
keywords, the pronoun swaps (I = YOU), the replies. Only two things are
built into Weizenbaum's code and must be supplied for another language:

- the delimiters: "." and "," and the word BUT, which cuts a sentence
  into clauses (in French: MAIS);
- the four messages printed when a script fails to match (NOMACH).

ENGLISH reproduces the original exactly. Other profiles are modern
additions, which may also:

- split elided words, so that a script can swap pronouns: in French
  J'AI is read as J' AI (then J' = VOUS, AI = AVEZ), and the reply is
  glued back together for display;
- list frequent words and letters, used to recognise the language of an
  input (see detect.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    delimiters: tuple[str, ...]
    nomatch_messages: tuple[str, str, str, str]  # indexed by LIMIT 1..4
    elisions: tuple[str, ...] = ()                # prefixes split from the next word
    common_words: frozenset[str] = frozenset()    # for language detection
    letters: str = ""                             # letters typical of the language
    # messages of the 1965 script editor (+): please instruct me, change not
    # recognized, list not found, memory list follows
    editor_messages: tuple[str, str, str, str] = (
        "PLEASE INSTRUCT ME", "CHANGE NOT RECOGNIZED", "LIST NOT FOUND", "MEMORY LIST FOLLOWS")

    def split_elisions(self, words: list[str]) -> list[str]:
        """["J'AI", "FAIM"] -> ["J'", "AI", "FAIM"]."""
        if not self.elisions:
            return words
        out = []
        for word in words:
            for prefix in self.elisions:
                if word.startswith(prefix) and len(word) > len(prefix):
                    out.append(prefix)
                    word = word[len(prefix):]
                    break
            out.append(word)
        return out

    def join_elisions(self, text: str) -> str:
        """"VOUS AVEZ DIT QU' IL" -> "VOUS AVEZ DIT QU'IL"."""
        if not self.elisions:
            return text
        return _elision_regex(self.elisions).sub(r"\1", text)


_cache: dict[tuple[str, ...], re.Pattern] = {}


def _elision_regex(elisions):
    if elisions not in _cache:
        alternatives = "|".join(re.escape(e) for e in elisions)
        _cache[elisions] = re.compile(r"(?<!\S)(%s) +(?=\S)" % alternatives)
    return _cache[elisions]


ENGLISH = Language(
    "en", "English",
    (",", ".", "BUT"),
    ("PLEASE CONTINUE", "HMMM", "GO ON , PLEASE", "I SEE"),
    common_words=frozenset("""
        THE A AN AND OR BUT IS ARE WAS WERE AM BE BEEN I ME MY MINE YOU YOUR
        YOURS HE SHE IT WE THEY THEM HIS HER OUR THEIR THIS THAT THESE THOSE
        WHAT WHY HOW WHEN WHERE WHO WHICH NOT NO YES DO DOES DON'T DIDN'T CAN
        CAN'T WON'T I'M YOU'RE IT'S HAVE HAS HAD WITH OF TO IN FOR FROM ABOUT
        AT BY ALL ALWAYS NEVER SOMETIMES BECAUSE IF THINK FEEL WANT NEED LIKE
        MOTHER FATHER SISTER BROTHER HELLO PERHAPS MAYBE VERY JUST
    """.split()),
)

FRENCH = Language(
    "fr", "Français",
    (",", ".", "MAIS"),
    ("CONTINUEZ , JE VOUS PRIE", "HMMM", "POURSUIVEZ , JE VOUS PRIE", "JE VOIS"),
    elisions=("JUSQU'", "LORSQU'", "PUISQU'", "QUOIQU'", "QU'",
              "J'", "L'", "D'", "M'", "T'", "S'", "N'", "C'"),
    common_words=frozenset("""
        LE LA LES UN UNE DES DU AU AUX ET OU EST SONT SUIS ÊTES ES ÉTAIT JE
        TU IL ELLE NOUS VOUS ILS ELLES MOI TOI ME TE SE MON MA MES TON TA TES
        VOTRE VOS NOTRE NOS LEUR CE CETTE CES QUE QUI QUOI POURQUOI COMMENT
        QUAND OÙ NE PAS PLUS JAMAIS OUI NON AVEC POUR DANS SUR SANS CHEZ PAR
        TRÈS AI AVEZ A PEUX POUVEZ VEUX VOULEZ FAIT TOUJOURS PARCE CAR SI
        BONJOUR MÈRE PÈRE SŒUR FRÈRE PEUT-ÊTRE J' L' D' M' N' C' QU' S'
    """.split()),
    letters="ÀÂÇÉÈÊËÎÏÔÛÙÜŸŒÆ",
    editor_messages=("VEUILLEZ M'INSTRUIRE", "MODIFICATION NON RECONNUE", "LISTE INTROUVABLE",
                     "VOICI LA LISTE DES MÉMOIRES"),
)

LANGUAGES = {lang.code: lang for lang in (ENGLISH, FRENCH)}


def get(code: str) -> Language:
    try:
        return LANGUAGES[code.lower()]
    except KeyError:
        raise ValueError(f"unknown language '{code}'; known: {', '.join(LANGUAGES)}") from None
