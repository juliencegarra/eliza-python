"""A faithful Python port of Joseph Weizenbaum's ELIZA (1966).

    >>> from eliza import Eliza, builtin_script
    >>> e = Eliza(builtin_script("doctor"))
    >>> e.response("Men are all alike.")
    'DID YOU THINK THEY MIGHT NOT BE ALL ALIKE'
"""

from __future__ import annotations

from importlib import resources

from . import languages
from .engine import Eliza
from .languages import ENGLISH, FRENCH, Language
from .multilingual import Conversation
from .script import Script, ScriptError, load, parse

__all__ = [
    "Eliza", "Conversation", "Script", "ScriptError", "Language", "ENGLISH", "FRENCH",
    "load", "parse", "builtin_script", "doctor", "BUILTIN_SCRIPTS",
]

__version__ = "0.1.0"

# public domain (CC0) scripts shipped with the package
BUILTIN_SCRIPTS = {
    "doctor": "doctor_1965_tape100.txt",          # Weizenbaum, MIT listing, March 1965
    "doctor-fr": "doctor_fr.txt",                 # French translation of the above
    "palindrome": "turing_palindrome.txt",        # Anthony Hay, 2022
    "equal-number": "turing_equal_number.txt",    # Anthony Hay, 2022
}


DOCTORS = {"en": "doctor", "fr": "doctor-fr"}


def doctor(language: str = "en", start: str = "en", **options) -> Eliza | Conversation:
    """The DOCTOR script in the given language, or in all of them with "auto"
    (the conversation then starts in `start` and follows the user's language).
    options are those of Eliza, e.g. version="1965"."""
    if language == "auto":
        start = start if start in DOCTORS else "en"
        return Conversation({code: doctor(code, **options) for code in DOCTORS}, start)
    if language not in DOCTORS:
        raise ValueError(f"no DOCTOR in '{language}'; known: {', '.join(DOCTORS)}, auto")
    return Eliza(builtin_script(DOCTORS[language]), languages.get(language), **options)


def builtin_script(name: str) -> Script:
    try:
        filename = BUILTIN_SCRIPTS[name]
    except KeyError:
        raise ValueError(f"unknown script '{name}'; built-in: {', '.join(BUILTIN_SCRIPTS)}") from None
    text = resources.files(__package__).joinpath("scripts", filename).read_text(encoding="utf-8")
    return parse(text)
