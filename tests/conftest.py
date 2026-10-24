from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cases import DIFFERENTIAL

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "references"
DATA = Path(__file__).resolve().parent / "data"
BUILTIN = ROOT / "eliza" / "scripts"
ORACLE = REFS / ("eliza_oracle.exe" if sys.platform == "win32" else "eliza_oracle")
GOLDEN = REFS / "golden.json"
OPTION = "/" if sys.platform == "win32" else "--"
# no processes in the browser: Pyodide uses the replies recorded in golden.json
CAN_RUN_ORACLE = sys.platform != "emscripten"


def reference(name: str) -> Path:
    path = REFS / name
    if not path.exists():
        pytest.skip(f"{name} missing: run  python tools/references.py fetch")
    return path


def prompts(name: str) -> list[str]:
    lines = (DATA / name).read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line.strip() and not line.startswith("#")]


def case_inputs(case: str) -> tuple[Path, list[str]]:
    script, inputs = DIFFERENTIAL[case]
    path = BUILTIN / script[len("builtin:"):] if script.startswith("builtin:") else reference(script)
    return path, prompts(inputs) if isinstance(inputs, str) else list(inputs)


def run_oracle(script: Path, inputs: list[str]) -> tuple[str, list[str]]:
    """Run eliza.cpp on inputs; return (hello message, replies)."""
    assert all(i.strip() and not i.startswith("*") for i in inputs)
    stdin = ("\n".join(inputs) + "\n\n").encode("utf-8")
    out = subprocess.run([str(ORACLE), OPTION + "nobanner", str(script)],
                         input=stdin, capture_output=True, check=True, timeout=120)
    lines = out.stdout.decode("utf-8").replace("\r\n", "\n").split("\n")
    # hello, then for each exchange an empty line and the reply
    return lines[0], lines[2::2][:len(inputs)]


def oracle_replies(case: str) -> tuple[list[str], str, list[str]]:
    """Return (inputs, hello, replies of eliza.cpp) for a differential case."""
    script, inputs = case_inputs(case)
    if CAN_RUN_ORACLE and ORACLE.exists():
        hello, replies = run_oracle(script, inputs)
        return inputs, hello, replies
    if GOLDEN.exists():
        recorded = json.loads(GOLDEN.read_text(encoding="utf-8")).get(case)
        if recorded and recorded["inputs"] == inputs:
            return inputs, recorded["hello"], recorded["replies"]
        pytest.skip(f"golden.json is stale for {case}: run  python tools/references.py golden")
    pytest.skip("no oracle: run  python tools/references.py oracle")
