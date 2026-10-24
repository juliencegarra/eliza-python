"""Historical conversations, to be replayed against this program.

None of them is shipped with the package: the transcripts and most of the
scripts they need are taken, when the user asks for them, from the
repositories that collected them (tools/references.py downloads them; the
web page fetches them at pinned commits):

- eliza.cpp by Anthony Hay, whose tests hold conversations with ELIZA found
  in archives and publications, each with the replies the 1966 DOCTOR
  script gives; where the historical reply differs, Hay kept it as a
  comment, which is shown here as "historical";
- the transcript of Weizenbaum's own code run on an emulated IBM 7094 by
  Rupert Lane (rupertl/eliza-ctss).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HAY = "https://raw.githubusercontent.com/anthay/ELIZA/4ac38e6694526f2a5c849014d3312a20cdddf842/"
CTSS = "https://raw.githubusercontent.com/rupertl/eliza-ctss/3af426b7da48224a55af682d0de1562c1af666ea/"

# where each source is found (file in references/, and URL)
SOURCES = {
    "eliza.cpp": HAY + "src/eliza.cpp",
    "doctor_1966_cacm.txt": HAY + "scripts/ELIZA-script-DOCTOR-original-1966-CACM-appendix.txt",
    "ctss_running_eliza.txt": CTSS + "etc/running-eliza.txt",
    "ctss_tape200.txt": CTSS + "eliza/src/ELIZA/tape.200",
}


@dataclass(frozen=True)
class Record:
    title: str
    year: str
    source: str        # "eliza.cpp:<array>" or "ctss:<script number>"
    script: str        # "builtin:<name>" or a SOURCES key
    version: str       # engine version that reproduces it
    note: str
    title_fr: str = ""
    note_fr: str = ""


CONVERSATIONS = {
    "cacm-1966": Record(
        "“Men are all alike” (Weizenbaum, CACM)", "1966",
        "eliza.cpp:weizenbaum_1966_cacm_conversation", "doctor_1966_cacm.txt", "1966",
        "The conversation printed in Weizenbaum's paper, with the script of its appendix.",
        "« Men are all alike » (Weizenbaum, CACM)",
        "La conversation imprimée dans l'article de Weizenbaum, avec le script de son annexe."),
    "ctss-100": Record(
        "The original code on CTSS, script 100", "1965",
        "ctss:100", "builtin:doctor", "1965",
        "Weizenbaum's MAD-SLIP code run on an emulated IBM 7094 by Rupert Lane (2024).",
        "Le code d'origine sur CTSS, script 100",
        "Le code MAD-SLIP de Weizenbaum exécuté sur un IBM 7094 émulé par Rupert Lane (2024)."),
    "ctss-200": Record(
        "The original code on CTSS, script 200", "1965",
        "ctss:200", "ctss_tape200.txt", "1965",
        "The same, with the 1966 script adapted by Rupert Lane: see “= DIT”.",
        "Le code d'origine sur CTSS, script 200",
        "Idem, avec le script de 1966 adapté par Rupert Lane : voir « = DIT »."),
    "alt-men-1966": Record(
        "“Men are all alike”, another version (MIT archives)", "1966",
        "eliza.cpp:weizenbaum_alt_men_are_all_alike_convo", "doctor_1966_cacm.txt", "1966",
        "A typed variant found in Weizenbaum's papers at MIT.",
        "« Men are all alike », autre version (archives du MIT)",
        "Une variante dactylographiée trouvée dans les papiers de Weizenbaum au MIT."),
    "unhappy-1966": Record(
        "“I am very unhappy these days” (MIT archives)", "1966",
        "eliza.cpp:weizenbaum_I_am_very_unhappy_these_days_convo", "doctor_1966_cacm.txt", "1966",
        "From the MIT Distinctive Collections.",
        "« I am very unhappy these days » (archives du MIT)",
        "Tirée des MIT Distinctive Collections."),
    "neumann-1966": Record(
        "Peter G. Neumann talks to ELIZA", "c. 1966",
        "eliza.cpp:the_peter_g_neumann_1966_conversation", "doctor_1966_cacm.txt", "1966",
        "Found in Neumann's papers by Paul McJones (2026).",
        "Peter G. Neumann parle à ELIZA",
        "Retrouvée dans les papiers de Neumann par Paul McJones (2026)."),
    "boston-globe-1966": Record(
        "The Boston Globe sees the doctor", "1966",
        "eliza.cpp:boston_globe_1966_conversation", "doctor_1966_cacm.txt", "1966",
        "Published by Robert L. Levey on 22 September 1966; the script used is unknown.",
        "Le Boston Globe chez le docteur",
        "Publiée par Robert L. Levey le 22 septembre 1966 ; le script utilisé est inconnu."),
    "explosion-1967": Record(
        "The Communications Explosion (film)", "1967",
        "eliza.cpp:weizenbaum_communications_explosion_1967_conversation",
        "doctor_1966_cacm.txt", "1966",
        "Weizenbaum demonstrates ELIZA, on film.",
        "The Communications Explosion (film)",
        "Weizenbaum fait une démonstration d'ELIZA, filmée."),
    "michie-1968": Record(
        "“Computer -- servant or master?” (Michie)", "1968",
        "eliza.cpp:michie_computer_servant_or_master_1968_conversation", "builtin:doctor", "1966",
        "Quoted by Donald Michie in Spectrum; reproduced with the 1965 TAPE 100 script.",
        "« Computer -- servant or master? » (Michie)",
        "Citée par Donald Michie dans Spectrum ; reproduite avec le script TAPE 100 de 1965."),
    "therapy-game-1977": Record(
        "The Therapy Game", "1977",
        "eliza.cpp:weizenbaum_july_1977_conversation", "doctor_1966_cacm.txt", "1966",
        "A conversation from July 1977.",
        "The Therapy Game",
        "Une conversation de juillet 1977."),
    "mind-machines-1978": Record(
        "The Mind Machines (film)", "1978",
        "eliza.cpp:weizenbaum_the_mind_machines_1978_conversation", "doctor_1966_cacm.txt", "1966",
        "Weizenbaum demonstrates ELIZA, on film.",
        "The Mind Machines (film)",
        "Weizenbaum fait une démonstration d'ELIZA, filmée."),
}


@dataclass(frozen=True)
class Exchange:
    prompt: str
    expected: str             # the reply of the reconstruction (eliza.cpp, or CTSS)
    historical: str | None    # the reply printed at the time, where it differs


_CPP_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|//([^\n]*)|/\*.*?\*/|([{},])', re.S)


def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", r"\1", s)


def from_eliza_cpp(cpp: str, array: str) -> list[Exchange]:
    """The { "prompt", "reply" } exchanges of an array of eliza.cpp."""
    found = re.search(r"const exchange %s\[\] = \{(.*?)\n\s*\};" % re.escape(array), cpp, re.S)
    if not found:
        raise ValueError(f"no array {array} in eliza.cpp")
    exchanges = []
    strings: list[str] = []
    comments: list[str] = []
    depth = 0
    pending_comma = False
    for m in _CPP_TOKEN.finditer(found.group(1)):
        string, comment, punct = m.groups()
        if punct == "{":
            depth += 1
            strings, comments, pending_comma = [], [], False
        elif punct == "}":
            depth -= 1
            if len(strings) == 2:
                old = [_unescape(c) for c in re.findall(r'"((?:[^"\\]|\\.)*)"', " ".join(comments))]
                exchanges.append(Exchange(strings[0], strings[1], old[-1] if old else None))
        elif depth == 1 and punct == ",":
            pending_comma = True
        elif depth == 1 and string is not None:
            if strings and not pending_comma:
                strings[-1] += _unescape(string)  # "adjacent" "literals"
            else:
                strings.append(_unescape(string))
            pending_comma = False
        elif depth == 1 and comment is not None and len(strings) == 1:
            comments.append(comment)
    return exchanges


def from_ctss(transcript: str, script_number: str) -> tuple[str, list[Exchange]]:
    """(hello, exchanges) of a session of the original code on CTSS."""
    sections = re.split(r"^=== Example of running with script (\d+).*$", transcript, flags=re.M)
    lines = sections[sections.index(script_number) + 1].splitlines()
    start = lines.index(script_number) + 1
    hello = " ".join(lines[start:lines.index("INPUT", start)])  # wrapped by the teletype
    exchanges = []
    for i, line in enumerate(lines):
        if line == "INPUT" and i + 1 < len(lines) and lines[i + 1].strip() \
                and lines[i + 1] != " QUIT,":
            j = i + 2
            while not lines[j].strip():
                j += 1
            exchanges.append(Exchange(lines[i + 1], lines[j], None))
    return hello, exchanges


def exchanges(record: Record, texts: dict[str, str]) -> list[Exchange]:
    """The exchanges of a record; texts maps SOURCES keys to their content."""
    kind, _, name = record.source.partition(":")
    if kind == "ctss":
        return from_ctss(texts["ctss_running_eliza.txt"], name)[1]
    return from_eliza_cpp(texts["eliza.cpp"], name)


def needed(record: Record) -> list[str]:
    """The SOURCES keys a record needs."""
    keys = ["ctss_running_eliza.txt" if record.source.startswith("ctss:") else "eliza.cpp"]
    if not record.script.startswith("builtin:"):
        keys.append(record.script)
    return keys


def replay(eliza, exchanges: list[Exchange]) -> list[dict]:
    """Give each prompt to eliza; compare with the recorded replies."""
    rows = []
    for e in exchanges:
        reply = eliza.response(e.prompt)
        rows.append(dict(prompt=e.prompt, reply=reply, expected=e.expected,
                         historical=e.historical, same=reply == e.expected))
    return rows


def session(record: Record, texts: dict[str, str]):
    """An ELIZA set up as the one that produced the record."""
    from . import Eliza, builtin_script, parse

    if record.script.startswith("builtin:"):
        script = builtin_script(record.script[len("builtin:"):])
    else:
        script = parse(texts[record.script])
    return Eliza(script, version=record.version, teaching=False)
