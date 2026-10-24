"""Conformance with historical records and with Anthony Hay's eliza.cpp.

The reference files are fetched by  python tools/references.py fetch
(they are not in the repository: most are (c) ACM); without them
these tests are skipped.
"""

from __future__ import annotations

import re

import pytest

from eliza import Eliza, ScriptError, builtin_script, history, load
from eliza.languages import ENGLISH
from eliza.script import parse

from cases import DIFFERENTIAL
from conftest import case_inputs, oracle_replies, reference


def _cpp_conversation(array_name: str) -> list[tuple[str, str]]:
    """Extract a { "prompt", "response" } array from eliza.cpp."""
    src = reference("eliza.cpp").read_text(encoding="utf-8")
    body = re.search(r"const exchange %s\[\] = \{(.*?)\n\};" % array_name, src, re.S).group(1)
    body = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("//"))
    pairs = re.findall(r'\{\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"\s*\}', body)
    return [(p.replace('\\"', '"'), r) for p, r in pairs]


def test_cacm_1966_conversation():
    """The conversation printed in Weizenbaum's 1966 paper, word for word."""
    eliza = Eliza(load(reference("doctor_1966_cacm.txt")))
    exchanges = _cpp_conversation("weizenbaum_1966_cacm_conversation")
    assert len(exchanges) == 15
    for prompt, expected in exchanges:
        assert eliza.response(prompt) == expected


def _ctss_transcript(script_number: str) -> list[tuple[str, str]]:
    text = reference("ctss_running_eliza.txt").read_text(encoding="utf-8")
    sections = re.split(r"^=== Example of running with script (\d+).*$", text, flags=re.M)
    part = sections[sections.index(script_number) + 1]
    lines = part.splitlines()
    pairs = []
    for i, line in enumerate(lines):
        if line == "INPUT" and i + 3 < len(lines) and lines[i + 1].strip():
            pairs.append((lines[i + 1], lines[i + 3]))
    return pairs


def test_original_code_on_ctss_tape_100():
    """Weizenbaum's own MAD-SLIP code, run on an emulated 7094 by Rupert Lane."""
    eliza = Eliza(builtin_script("doctor"))
    exchanges = _ctss_transcript("100")
    assert len(exchanges) == 15
    for prompt, expected in exchanges:
        # TREAD put punctuation in cells of its own: "REALLY , EVERYONE"
        assert eliza.response(prompt) == expected.replace(" ,", ",")


@pytest.mark.parametrize("name", [
    "doctor_1966_cacm.txt", "doctor_fr_jeu_de_paume.txt", "yapyap_modified.txt"])
def test_reference_scripts_parse(name):
    script = load(reference(name))
    assert script.rules and script.none.transformations


def test_tape_102_is_ill_formed():
    # (DON'T YOU KNOW) is out of place in this listing, as Hay notes
    with pytest.raises(ScriptError):
        load(reference("doctor_1965_tape102.txt"))


# ---------------------------------------------------------------------------
# differential tests: same inputs, same replies as eliza.cpp


@pytest.mark.parametrize("case", DIFFERENTIAL)
def test_same_replies_as_eliza_cpp(case):
    inputs, hello, expected = oracle_replies(case)
    assert len(expected) == len(inputs)
    # eliza.cpp knows no language profile: compare with the historical one
    eliza = Eliza(load(case_inputs(case)[0]), ENGLISH, teaching=False)
    assert eliza.hello() == hello
    for prompt, reply in zip(inputs, expected):
        assert eliza.response(prompt) == reply, prompt


def test_parse_errors_like_eliza_cpp():
    with pytest.raises(ScriptError, match="no NONE rule"):
        parse("(HELLO) (MEMORY X (0 = A)(0 = B)(0 = C)(0 = D)) (X ((0) (Y)))")
    with pytest.raises(ScriptError, match="out of range"):
        parse("(HELLO) (X ((0 X) (3))) (NONE ((0) (OK)))")


@pytest.mark.parametrize("key", history.CONVERSATIONS)
def test_historical_conversations_replay(key):
    """Every conversation of eliza.history gives the recorded replies."""
    record = history.CONVERSATIONS[key]
    texts = {name: reference(name).read_text(encoding="utf-8") for name in history.needed(record)}
    rows = history.replay(history.session(record, texts), history.exchanges(record, texts))
    assert len(rows) >= 4
    assert [r["reply"] for r in rows] == [r["expected"] for r in rows]
