// Run the eliza-python test suite inside Pyodide (CPython compiled to
// WebAssembly), under Node.js:
//
//     cd tools/pyodide && npm install && npm test
//
// The repository is mounted read-write at /repo; pytest is loaded from the
// Pyodide distribution (downloaded once from jsDelivr, then cached).
// Differential tests use references/golden.json, recorded on the host by
// `python tools/references.py golden`, since Pyodide cannot start eliza.cpp.

import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..");

const pyodide = await loadPyodide();
const { version } = pyodide;
pyodide.mountNodeFS("/repo", repo);
await pyodide.loadPackage("pytest", { messageCallback: () => {} });

const args = ["-q", "-rs", "-p", "no:cacheprovider", ...process.argv.slice(2)];
pyodide.globals.set("pytest_args", pyodide.toPy(args));
const status = await pyodide.runPythonAsync(`
import os, sys, pytest
os.chdir("/repo")
sys.dont_write_bytecode = True   # keep __pycache__ out of the mounted repository
print(f"Pyodide ${version}, Python {sys.version.split()[0]}, platform {sys.platform}")
int(pytest.main(list(pytest_args)))
`);
process.exit(Number(status));
