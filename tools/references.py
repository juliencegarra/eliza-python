"""Fetch the reference material used by the conformance tests.

These files are NOT part of this repository, for licence reasons: the
1966 DOCTOR script and conversation are from an ACM
publication, and the French script is a translation of that script. They
are downloaded, at pinned commits, into references/ (git-ignored).

    python tools/references.py fetch     # download the files
    python tools/references.py oracle    # also compile eliza.cpp with g++
    python tools/references.py golden    # also record its replies (for Pyodide)

The compiled eliza.cpp (Anthony Hay, CC0) is the oracle of the
differential tests: tests/test_reference.py feeds the same inputs to
both programs and expects the same replies. Where no process can be
started (Pyodide), the replies recorded in references/golden.json are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "references"

HAY = "https://raw.githubusercontent.com/anthay/ELIZA/4ac38e6694526f2a5c849014d3312a20cdddf842/"
CTSS = "https://raw.githubusercontent.com/rupertl/eliza-ctss/3af426b7da48224a55af682d0de1562c1af666ea/"

FILES = {
    "eliza.cpp": HAY + "src/eliza.cpp",
    "doctor_1966_cacm.txt": HAY + "scripts/ELIZA-script-DOCTOR-original-1966-CACM-appendix.txt",
    "doctor_fr_jeu_de_paume.txt": HAY + "scripts/ELIZA-script-DOCTOR-French-Jeu-de-Paume.txt",
    "doctor_1965_tape102.txt": HAY + "scripts/ELIZA-script-02-000311051-1965-03-06-TAPE-102.txt",
    "yapyap_modified.txt": HAY + "scripts/ELIZA-script-YAPYAP-modified-for-1966-CACM-ELIZA.txt",
    "ctss_running_eliza.txt": CTSS + "etc/running-eliza.txt",
    # the CACM script as adapted by Rupert Lane for the 1965 code (script 200)
    "ctss_tape200.txt": CTSS + "eliza/src/ELIZA/tape.200",
}

ORACLE = REFS / ("eliza_oracle.exe" if sys.platform == "win32" else "eliza_oracle")


def fetch() -> None:
    REFS.mkdir(exist_ok=True)
    for name, url in FILES.items():
        target = REFS / name
        if target.exists():
            print(f"already present: {target.relative_to(ROOT)}")
            continue
        print(f"fetching {url}")
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        target.write_bytes(data)
        print(f"  -> {target.name} ({len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()[:16]})")


def build_oracle() -> None:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        sys.exit("no C++ compiler (g++ or clang++) found")
    cmd = [compiler, "-std=c++20", "-O2", "-o", str(ORACLE), str(REFS / "eliza.cpp")]
    if sys.platform == "win32":
        cmd.insert(1, "-static")  # no dependency on the MinGW runtime DLLs
    print("compiling the oracle (about a minute):")
    print("  " + " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"oracle ready: {ORACLE.relative_to(ROOT)}  (python -m pytest now runs the differential tests)")


def record_golden() -> None:
    """Record the oracle's replies, for platforms that cannot run it (Pyodide)."""
    sys.path[:0] = [str(ROOT / "tests")]
    import conftest
    from cases import DIFFERENTIAL

    golden = {}
    for case in DIFFERENTIAL:
        script, inputs = conftest.case_inputs(case)
        hello, replies = conftest.run_oracle(script, inputs)
        golden[case] = {"inputs": inputs, "hello": hello, "replies": replies}
    conftest.GOLDEN.write_text(json.dumps(golden, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {conftest.GOLDEN} ({len(golden)} cases)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["fetch", "oracle", "golden"])
    args = parser.parse_args()
    fetch()
    if args.action == "oracle" or (args.action == "golden" and not ORACLE.exists()):
        build_oracle()
    if args.action == "golden":
        record_golden()


if __name__ == "__main__":
    main()
