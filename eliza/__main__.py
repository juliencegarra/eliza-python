"""Command line: python -m eliza [script] [--lang fr] ..."""

from __future__ import annotations

import argparse
import locale
import sys
from pathlib import Path

from . import BUILTIN_SCRIPTS, DOCTORS, Conversation, Eliza, builtin_script, languages, load


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eliza", description="Joseph Weizenbaum's ELIZA (1966), ported to Python.")
    parser.add_argument(
        "script", nargs="?", default="doctor",
        help=f"a script file, or one of: {', '.join(BUILTIN_SCRIPTS)} (default: doctor)")
    parser.add_argument(
        "--lang", help=f"{', '.join(languages.LANGUAGES)} or auto. With the doctor script: "
        "the DOCTOR in that language, auto following the language of each input. "
        "With another script: delimiters and built-in messages "
        "(default: the script's eliza-language, else en)")
    parser.add_argument(
        "--fold-accents", action="store_true",
        help="ignore accents in the input (the script must be written without accents)")
    parser.add_argument(
        "--none-on-error", action="store_true",
        help="answer from the NONE rule instead of the built-in messages on script errors")
    args = parser.parse_args(argv)
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")

    options = dict(use_nomatch_msgs=not args.none_on_error, fold_input_accents=args.fold_accents)
    if args.script == "doctor" and args.lang and not Path(args.script).is_file():
        if args.lang == "auto":
            sessions = {code: Eliza(builtin_script(name), languages.get(code), **options)
                        for code, name in DOCTORS.items()}
            start = locale.getlocale()[0] or "en"
            eliza = Conversation(sessions, start[:2] if start[:2] in sessions else "en")
        else:
            eliza = Eliza(builtin_script(DOCTORS[args.lang]), languages.get(args.lang), **options)
    else:
        script = load(args.script) if Path(args.script).is_file() else builtin_script(args.script)
        lang = args.lang if args.lang not in (None, "auto") else script.metadata.get("language", "en")
        eliza = Eliza(script, languages.get(lang), **options)

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
        print(" ".join(eliza.response(line).split()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
