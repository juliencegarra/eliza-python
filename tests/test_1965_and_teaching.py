"""The 1965 version (recovered listing) and teaching ELIZA during a conversation."""

from __future__ import annotations

import re

import pytest

from eliza import Eliza, builtin_script, load, parse
from eliza.script import to_text

from conftest import reference


def _ctss(script_number: str):
    """(hello, [(prompt, reply)]) of the original code run on CTSS by Rupert Lane."""
    text = reference("ctss_running_eliza.txt").read_text(encoding="utf-8")
    sections = re.split(r"^=== Example of running with script (\d+).*$", text, flags=re.M)
    lines = sections[sections.index(script_number) + 1].splitlines()
    start = lines.index(script_number) + 1
    end = lines.index("INPUT", start)
    hello = " ".join(lines[start:end])  # the teletype wrapped it at 80 columns
    exchanges = []
    for i, line in enumerate(lines):
        if line == "INPUT" and lines[i + 1].strip() and lines[i + 1] != " QUIT,":
            j = i + 2
            while not lines[j].strip():
                j += 1
            exchanges.append((lines[i + 1], lines[j]))
    return hello, exchanges


@pytest.mark.parametrize("number", ["100", "200"])
def test_1965_version_as_on_ctss(number):
    """The original code on an emulated IBM 7094: same replies, same spacing."""
    script = builtin_script("doctor") if number == "100" else load(reference("ctss_tape200.txt"))
    eliza = Eliza(script, version="1965")
    hello, exchanges = _ctss(number)
    assert eliza.hello() == hello
    assert len(exchanges) == 15
    for prompt, reply in exchanges:
        assert eliza.response(prompt) == reply, prompt


SCRIPT = """
(HELLO)
(EVERYONE 2 ((0) (WHO IN PARTICULAR)))
(EVERYONEX 3 ((0) (NEVER FOUND BY THE OLD CODE)))
(ALIKE 10 ((0 ALIKE 0) (=DIT) (NEWKEY) (PRE (1 SIMILAR 3) (=SAME))))
(SAME ((0) (SAME 1)))
(DIT ((0) (IN WHAT WAY)))
(SAD ((0 (*HAPPY WONDERFUL) 0) (FEELING 2)) ((0) (SAD)))
(WHY (=WHAT))
(WHAT ((0) (WHY DO YOU ASK, FRIEND)))
(MEMORY SAD (0 = A 1) (0 = B 1) (0 = C 1) (0 = D 1))
(NONE ((0) (GO ON)))
"""


def test_1965_differences():
    old, new = Eliza(parse(SCRIPT), version="1965"), Eliza(parse(SCRIPT))
    # a keyword sharing its first 6 characters with an earlier one is never found
    assert old.response("everyonex") == "GO ON"
    assert new.response("everyonex") == "NEVER FOUND BY THE OLD CODE"
    # reassembly links, NEWKEY and PRE do not exist: they are printed
    assert old.response("they are alike") == "= DIT"
    assert new.response("they are alike") == "IN WHAT WAY"
    assert old.response("they are alike") == "NEWKEY"
    assert old.response("they are alike") == "PRE 1 SIMILAR 3 = SAME"
    # a link in place of a transformation is followed in both
    assert old.response("why") == "WHY DO YOU ASK , FRIEND"
    # (*...) choices compare 6-character cells: WONDER is the first cell of WONDERFUL
    assert old.response("sad wonder") == "FEELING WONDER"
    assert new.response("sad wonder") == "SAD"


def test_teaching_a_new_rule_as_on_ctss():
    # the session shown in Anthony Hay's annotated transcription, run on CTSS
    for version in ("1965", "1966"):
        eliza = Eliza(load(reference("ctss_tape200.txt")), version=version)
        assert eliza.response("hi eliza") == "I AM NOT SURE I UNDERSTAND YOU FULLY"
        assert eliza.response("* hi ((hi eliza) (how do you do)) ((hi 0) (hello from 2))") == ""
        assert eliza.response("hi eliza") == "HOW DO YOU DO"
        assert eliza.response("hi freddy") == "HELLO FROM FREDDY"
        assert eliza.modified


def test_script_editor():
    eliza = Eliza(builtin_script("doctor"))
    assert eliza.response("+") == "PLEASE INSTRUCT ME"
    assert eliza.response("TYPE NO").startswith("(NO\n    ((0)\n        (ARE YOU SAYING 'NO'")
    assert eliza.response("SUBST NO (WHY NOT) (WHY NOT INDEED)") == "PLEASE INSTRUCT ME"
    assert eliza.response("APPEND NO (WHY 'NO') (NEGATIVE AGAIN)") == "PLEASE INSTRUCT ME"
    assert eliza.response("ADD YES ((0 YES 0 SURE 0) (SURE OF 5))") == "PLEASE INSTRUCT ME"
    assert eliza.response("RANK YES 7") == "PLEASE INSTRUCT ME"
    assert eliza.response("TYPE NOTHERE") == "LIST NOT FOUND\nPLEASE INSTRUCT ME"
    assert eliza.response("SUBST NO (NOT THERE) (X)") == "LIST NOT FOUND\nPLEASE INSTRUCT ME"
    assert eliza.response("FROBNICATE") == "CHANGE NOT RECOGNIZED\nPLEASE INSTRUCT ME"
    display = eliza.response("DISPLA")
    assert "*\n(NO\n" in display and "\n 24\n" in display and "MEMORY LIST FOLLOWS" in display
    assert eliza.response("START") == ""
    assert not eliza.editing

    replies = [eliza.response("no") for _ in range(5)]
    assert replies == ["ARE YOU SAYING 'NO' JUST TO BE NEGATIVE", "YOU ARE BEING A BIT NEGATIVE",
                       "WHY NOT INDEED", "WHY 'NO'", "NEGATIVE AGAIN"]
    # YES now outranks I (rank 0) and its added decomposition is tried after (0)
    assert eliza.response("yes I am sure of it") == "YOU SEEM QUITE POSITIVE"


def test_taught_script_is_saved_and_others_untouched():
    script = builtin_script("doctor")
    eliza = Eliza(script)
    eliza.response("* hi ((hi 0) (hello from 2))")
    saved = parse(eliza.script_text())
    assert "HI" in saved.rules and "HI" not in script.rules
    assert Eliza(saved).response("hi freddy") == "HELLO FROM FREDDY"
    assert to_text(parse(to_text(script))) == to_text(script)


def test_teaching_errors_and_limit():
    eliza = Eliza(builtin_script("doctor"))
    assert "REFERENCED KEYWORD DOES NOT EXIST" in eliza.response("* hi ((0) (=NOWHERE))")
    assert eliza.limit == 2  # "*" lines go through the main loop, as in 1965
    eliza.response("+")
    eliza.response("TYPE YES")
    assert eliza.limit == 3  # editor commands do not
    # teaching can be turned off: "+" is then an ordinary word
    assert Eliza(builtin_script("doctor"), teaching=False).response("+") == \
        "I AM NOT SURE I UNDERSTAND YOU FULLY"


def test_link_loops_end():
    loop = parse("(HI) (A (=B)) (B (=A)) (MEMORY A (0 = A)(0 = B)(0 = C)(0 = D)) (NONE ((0) (X)))")
    for version in ("1965", "1966"):
        assert Eliza(loop, version=version).response("a") == "HMMM"


def test_empty_input_after_pre():
    # PRE may empty the input: no memory can be made of it (no crash)
    script = parse("(HI) (MY = YOUR ((0 YOUR 0) (PRE () (=MY))))"
                   " (MEMORY MY (0 = A)(0 = B)(0 = C)(0 = D)) (NONE ((0) (X)))")
    assert Eliza(script).response("my cat") == "HMMM"


def test_lone_surrogates_do_not_crash():
    assert Eliza(builtin_script("doctor")).response("my \udcff \ud800")


def test_trace_steps_for_the_step_by_step_display():
    eliza = Eliza(builtin_script("doctor"))
    eliza.response("Well, my boyfriend made me come here.")
    steps = eliza.trace.steps
    assert steps["discarded"] == ["WELL ,"]
    assert steps["keystack"] == ["MY"]   # ME = YOU is a substitution only
    assert steps["clause"] == "YOUR BOYFRIEND MADE YOU COME HERE"
    assert steps["cut"] == "."
    # the memory of the 1966 paper: HASH of HERE picks the 4th transformation
    assert steps["memory_new"]["index"] == 4 and steps["memory_new"]["last_word"] == "HERE"
    rule = steps["rules"][0]
    assert (rule["keyword"], rule["decomposition"], rule["choice"]) == ("MY", "0 YOUR 0", "1/4")
    assert rule["components"] == ["", "YOUR", "BOYFRIEND MADE YOU COME HERE"]
    assert steps["source"] == "rule" and steps["reply"] == "YOUR BOYFRIEND MADE YOU COME HERE"
    eliza.response("I need some help, that much seems certain.")
    assert eliza.trace.steps["cut"] == ", THAT MUCH SEEMS CERTAIN ."
