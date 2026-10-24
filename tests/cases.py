"""The differential test cases, shared by the tests and tools/references.py."""

from __future__ import annotations

# case -> (script, prompt file in tests/data or literal inputs)
# a script name is looked up in references/, unless it starts with "builtin:"
DIFFERENTIAL = {
    "tape100-en": ("builtin:doctor_1965_tape100.txt", "prompts_en.txt"),
    "cacm-en": ("doctor_1966_cacm.txt", "prompts_en.txt"),
    "yapyap-en": ("yapyap_modified.txt", "prompts_en.txt"),
    "french-fr": ("doctor_fr_jeu_de_paume.txt", "prompts_fr.txt"),
    # our French DOCTOR, without the fr profile (eliza.cpp splits no elisions)
    "doctor-fr": ("builtin:doctor_fr.txt", "prompts_fr.txt"),
    "palindrome": ("builtin:turing_palindrome.txt",
                   ["PALP A B B A", "PALP A A A B B", "PALP B A B", "PALP A B"]),
    "equal-number": ("builtin:turing_equal_number.txt",
                     ["EQUAL A B B A", "EQUAL A A A B B", "EQUAL A A B B B A A B"]),
}
