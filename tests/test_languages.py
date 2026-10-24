"""Language profiles, the French DOCTOR and the automatic choice of language."""

from __future__ import annotations

import pytest

from eliza import ENGLISH, FRENCH, Conversation, Eliza, builtin_script, doctor
from eliza.hollerith import last_chunk_as_bcd, slip_hash
from eliza.multilingual import detect, vocabulary


def test_elisions_split_and_joined():
    assert FRENCH.split_elisions(["J'AI", "DIT", "QU'IL", "L'", "AUJOURD'HUI"]) == \
        ["J'", "AI", "DIT", "QU'", "IL", "L'", "AUJOURD'HUI"]
    assert FRENCH.join_elisions("VOUS DITES QU' IL S' OCCUPE DE L' OCÉAN") == \
        "VOUS DITES QU'IL S'OCCUPE DE L'OCÉAN"
    # English is untouched: the historical behaviour
    assert ENGLISH.split_elisions(["I'M", "L'AMOUR"]) == ["I'M", "L'AMOUR"]
    assert ENGLISH.join_elisions("L' AMOUR") == "L' AMOUR"


def test_french_delimiter():
    # MAIS cuts the sentence, as BUT does in English: JE RESTE is dropped
    text = "Je pense que mon travail me tue mais je reste."
    assert doctor("fr").response(text) == "VOUS DITES QUE VOUS PENSE QUE VOTRE TRAVAIL VOUS TUE"
    # with the historical profile, only BUT is a delimiter
    english_profile = Eliza(builtin_script("doctor-fr"), ENGLISH)
    assert english_profile.response(text).endswith("MAIS VOUS RESTE")


# the memory laid down by "Mon travail me prend tout mon temps.": HASH of
# the last cell, TEMPS, picks one of the four MEMORY transformations
MEMORY = ("PARLONS ENCORE DE", "TOUT À L'HEURE, VOUS DISIEZ QUE", "MAIS",
          "CELA A-T-IL UN RAPPORT AVEC LE FAIT QUE")[
    slip_hash(last_chunk_as_bcd("TEMPS"), 2)] + " VOTRE TRAVAIL VOUS PREND TOUT VOTRE TEMPS"

# a French conversation with the built-in (CC0) French DOCTOR
FRENCH_EXCHANGES = [
    ("Les hommes sont tous pareils.", "VRAIMENT, TOUS"),
    ("Je suis très fatigué en ce moment.",
     "EST-CE PARCE QUE VOUS ÊTES TRÈS FATIGUÉ EN CE MOMENT QUE VOUS ÊTES VENU ME VOIR"),
    ("Vous êtes une machine, n'est-ce pas ?", "QU'EST-CE QUI VOUS FAIT PENSER QUE JE SUIS UNE MACHINE"),
    ("Mon travail me prend tout mon temps.", "VOTRE TRAVAIL VOUS PREND TOUT VOTRE TEMPS"),
    ("J'ai rêvé de l'océan cette nuit.", "VOUS DITES QUE VOUS AVEZ RÊVÉ DE L'OCÉAN CETTE NUIT"),
    ("Je me sens seul.", "PARLEZ-MOI DAVANTAGE DE CE QUE VOUS RESSENTEZ"),
    ("Ma mère s'occupe de moi.", "PARLEZ-MOI DAVANTAGE DE VOTRE FAMILLE"),
    ("Ma mère s'occupe de moi.", "QUI D'AUTRE DANS VOTRE FAMILLE S'OCCUPE DE VOUS"),
    ("Je ne peux pas dormir.", "COMMENT SAVEZ-VOUS QUE VOUS NE POUVEZ PAS DORMIR"),
    ("Êtes-vous un vrai docteur ?", "POURQUOI VOUS DEMANDEZ-VOUS SI JE SUIS UN VRAI DOCTEUR OU NON"),
    # 11th reply, LIMIT is 4 and there is no keyword: the first memory comes back
    ("Il pleut.", MEMORY),
    ("Pouvez-vous m'aider ?", "VOUS CROYEZ QUE JE LE PEUX, N'EST-CE PAS"),
]


def test_french_doctor_conversation():
    eliza = doctor("fr")
    assert eliza.hello().startswith("BONJOUR. JE SUIS LE DOCTEUR.")
    for prompt, reply in FRENCH_EXCHANGES:
        assert eliza.response(prompt) == reply, prompt


@pytest.mark.parametrize("text,expected", [
    ("Men are all alike.", "en"),
    ("I am unhappy.", "en"),
    ("Why?", "en"),
    ("Je suis malheureux.", "fr"),
    ("Pourquoi ?", "fr"),
    ("Ma sœur ne m'écoute jamais.", "fr"),
    ("Désolée.", "fr"),            # accents alone are evidence
    ("Paris.", None),               # no evidence: keep the current language
    ("OK", None),
])
def test_detect(text, expected):
    candidates = {"en": (ENGLISH, vocabulary(ENGLISH)), "fr": (FRENCH, vocabulary(FRENCH))}
    assert detect(text, candidates) == expected


def test_conversation_follows_the_language():
    conversation = doctor("auto", start="fr")
    assert isinstance(conversation, Conversation)
    assert conversation.hello().startswith("BONJOUR")
    assert conversation.response("Men are all alike.") == "DID YOU THINK THEY MIGHT NOT BE ALL ALIKE"
    assert conversation.language == "en"
    assert conversation.response("Paris.") == "I AM NOT SURE I UNDERSTAND YOU FULLY"  # stays English
    assert conversation.response("Je suis triste.") == \
        "EST-CE PARCE QUE VOUS ÊTES TRISTE QUE VOUS ÊTES VENU ME VOIR"
    assert conversation.language == "fr"
    # each language keeps its own state: the English LIMIT went on from 3
    assert conversation.response("Yes.") == "YOU SEEM QUITE POSITIVE"


def test_unknown_start_language_falls_back_to_english():
    assert doctor("auto", start="de").language == "en"
