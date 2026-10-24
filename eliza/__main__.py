"""Command line: python -m eliza [script] [--lang fr|auto] [--version 1965] ..."""

from __future__ import annotations

import argparse
import locale
import re
import sys
from pathlib import Path

from . import BUILTIN_SCRIPTS, DOCTORS, Conversation, Eliza, ScriptError, builtin_script, \
    languages, load
from .engine import VERSIONS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eliza", description="Joseph Weizenbaum's ELIZA (1966), ported to Python.",
        epilog="During the conversation: '+' opens the script editor (TYPE, SUBST, APPEND, "
               "ADD, RANK, DISPLA, START), '* KEYWORD ((pattern) (reply))' teaches a new rule, "
               "'*' alone shows how the last reply was made, an empty line ends.")
    parser.add_argument(
        "script", nargs="?", default="doctor",
        help=f"a script file, or one of: {', '.join(BUILTIN_SCRIPTS)} (default: doctor)")
    parser.add_argument(
        "--lang", choices=[*languages.LANGUAGES, "auto"],
        help="with the doctor script: the DOCTOR in that language, auto following the "
             "language of each input; with another script: delimiters and built-in messages "
             "(default: the script's eliza-language, else en)")
    parser.add_argument(
        "--version", choices=VERSIONS, default="1966",
        help="1966: as described in the CACM paper (default); 1965: the recovered listing")
    parser.add_argument(
        "--fold-accents", action="store_true",
        help="ignore accents in the input (the script must be written without accents)")
    parser.add_argument(
        "--none-on-error", action="store_true",
        help="answer from the NONE rule instead of the built-in messages on script errors")
    args = parser.parse_args(argv)
    for stream in (sys.stdin, sys.stdout):
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")

    options = dict(version=args.version, use_nomatch_msgs=not args.none_on_error,
                   fold_input_accents=args.fold_accents)
    try:
        if args.script == "doctor" and args.lang and not Path(args.script).is_file():
            if args.lang == "auto":
                sessions = {code: Eliza(builtin_script(name), languages.get(code), **options)
                            for code, name in DOCTORS.items()}
                start = (locale.getlocale()[0] or "en")[:2]
                eliza = Conversation(sessions, start if start in sessions else "en")
            else:
                eliza = Eliza(builtin_script(DOCTORS[args.lang]), languages.get(args.lang),
                              **options)
        else:
            script = load(args.script) if Path(args.script).is_file() \
                else builtin_script(args.script)
            lang = args.lang if args.lang not in (None, "auto") \
                else script.metadata.get("language", "en")
            eliza = Eliza(script, languages.get(lang), **options)
    except (ScriptError, ValueError, OSError) as error:
        parser.error(str(error))

    print(eliza.hello())
    print("(empty line to quit, * to show how the last reply was made)")
    while True:
        try:
            line = input("\n> ")
        except EOFError:
            break
        if not line.strip():
            break
        if line.strip() == "*":
            print(eliza.trace.text())
            continue
        # display only: scripts may hold blank words (a « quote » becomes a
        # space), which the engine keeps to stay identical to eliza.cpp
        print("\n".join(re.sub(r"(?<=\S) {2,}(?=\S)", " ", row).rstrip()
                        for row in eliza.response(line).split("\n")))

    sessions = eliza.sessions.values() if isinstance(eliza, Conversation) else [eliza]
    for session in sessions:
        if session.modified:
            # ENDPLA: "WHAT IS TO BE THE NUMBER OF THE NEW SCRIPT"
            try:
                name = input(f"\nthe script was taught new rules; file to save it "
                             f"({session.language.code}, empty: don't save): ").strip()
            except EOFError:
                name = ""
            if name:
                Path(name).write_text(session.script_text(), encoding="utf-8")
                print(f"saved to {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
