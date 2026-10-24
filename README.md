# eliza-python

A Python port of Joseph Weizenbaum's ELIZA (1966), **true to the original**:
given the same input and the same script, it gives the same reply.

- It reproduces word for word the conversation published in *CACM* in 1966.
- In its 1965 version, it reproduces the runs of the original MAD-SLIP code on an
  emulated IBM 7094 (CTSS), down to the spacing of punctuation and the stray “= DIT”.
- It replays eleven historical conversations (1965–1978), 278 exchanges in all.
- It gives the same replies as Anthony Hay's C++ reconstruction (`eliza.cpp`), which the
  tests use as an oracle.
- It needs only the Python ≥ 3.9 standard library, and runs under Pyodide.

**Try it in the browser:** <https://juliencegarra.github.io/eliza-python/>

## Usage

```bash
python -m eliza                       # DOCTOR, the March 1965 script (public domain)
python -m eliza --lang fr             # the same DOCTOR, translated into French
python -m eliza --lang auto           # follows the language of each sentence (English / French)
python -m eliza --version 1965        # the program of the 1965 listing, as it was
python -m eliza my_script.txt --lang fr
```

An empty line quits. `*` on its own shows how the last reply was built.

```python
from eliza import doctor
eliza = doctor()                                # or doctor("fr"), doctor("auto")
print(eliza.hello())
print(eliza.response("Men are all alike."))   # DID YOU THINK THEY MIGHT NOT BE ALL ALIKE
```

## Two historical versions

- **`1966`** (default): the program described in the *CACM* paper. It keeps a stack of
  keywords and handles `NEWKEY`, `PRE` and `=WORD` links.
- **`1965`**: the program of the listing found at MIT. It keeps a single keyword, has
  neither `NEWKEY` nor `PRE`, and prints a link found in a reply as it is (“= DIT”). Words
  are compared on their first 6 characters, and punctuation is printed apart. This mode is
  checked against the original code running on CTSS.

## ELIZA learns during the conversation

This was there from 1965 (hence the name ELIZA, after Eliza Doolittle), then lost in every
clone:

- **`* KEYWORD ((pattern) (reply) ...)`** adds a rule. For example,
  `* HI ((HI 0) (HELLO FROM 2))`, after which “hi freddy” gets “HELLO FROM FREDDY”.
- **`+`** opens the editor, which answers `PLEASE INSTRUCT ME`:
  - `TYPE KEYWORD` shows a rule;
  - `SUBST KEYWORD (old) (new)` replaces a reply;
  - `APPEND KEYWORD (existing) (new)` adds a reply;
  - `ADD KEYWORD ((pattern) (reply))` adds a decomposition;
  - `RANK KEYWORD n` changes the rank of a keyword;
  - `DISPLA` shows the whole script;
  - `START` goes back to the conversation.
- **Saving**: at the end of the session, the modified script can be saved
  (`Eliza.script_text()`).

## Scripts

The package ships only public-domain scripts:

- `doctor`: TAPE 100, found with the code at MIT;
- `doctor-fr`: its French translation, written for this project (CC0);
- two Turing machines by Anthony Hay.

In `auto` mode, each sentence goes to the DOCTOR of its language. The language is
recognised from common words, the script's keywords and accented letters; when there is
no clue, the conversation stays in the current language.

The DOCTOR of the 1966 paper and its French translation can still be used, but are not
shipped (© ACM):

```bash
python tools/references.py fetch
python -m eliza references/doctor_1966_cacm.txt
python -m eliza references/doctor_fr_jeu_de_paume.txt --lang fr
```

## In the browser

`web/index.html` loads Pyodide from jsDelivr and reads the `eliza/` package next to it, so
the root of the repository must be served over HTTP:

```bash
python -m http.server 8765 --bind 127.0.0.1
```

then open <http://127.0.0.1:8765/web/>. The page is in English or French (detected from the
browser) and offers:

- **settings** (gear icon): the script, the language of the conversation (or automatic
  detection), the version of the program (1965 or 1966) and the display. The DOCTOR of the
  1966 paper (© ACM) is offered there by reading it on demand from Anthony Hay's
  repository, without redistributing it;
- a **teletype** display: continuous paper, 80 columns and the `INPUT` prompt as on CTSS,
  printed at 14.8 characters a second like the IBM 2741, or instantly;
- the **how it works** panel: click any reply to see, step by step, the reading of the
  sentence and the `LIMIT` counter, the keywords and substitutions, the numbered
  decomposition, the reassembly and the memory queue;
- the **historical conversations** (book icon), replayed in the conversation itself, with
  what the archive gave instead noted under the replies that differ; you can then go on
  talking to that ELIZA. Their texts are downloaded on demand from Anthony Hay's and
  Rupert Lane's repositories, without being redistributed;
- **teaching** (`*`, `+`) and downloading the modified script;
- a **new conversation** icon.

## Tests

```bash
python tools/references.py oracle     # references + build of eliza.cpp (g++)
python -m pytest
```

### Under Pyodide (WebAssembly)

The same test suite runs in Pyodide 314.0.7 (Python 3.14) under Node.js. Pyodide cannot
run the C++ oracle, so the expected replies are recorded beforehand on the host machine.

```bash
python tools/references.py golden     # records references/golden.json
cd tools/pyodide && npm install && npm test
```

## Credits

- Joseph Weizenbaum, for ELIZA and the DOCTOR script.
- Jeff Shrager and the [ELIZAGEN](https://elizagen.org/) team, who found the original code
  and gathered its history.
- Anthony Hay, for `eliza.cpp`, the scripts and the conversations collected in
  [anthay/ELIZA](https://github.com/anthay/ELIZA).
- Rupert Lane, for running the original code on CTSS in
  [rupertl/eliza-ctss](https://github.com/rupertl/eliza-ctss).

## Licence

- The code is under the [MIT](LICENSE) licence.
- The scripts in `eliza/scripts/` are in the public domain (CC0 1.0): TAPE 100 comes from
  Weizenbaum's MIT listing (CC0, Weizenbaum estate), its French translation was written for
  this project, and the Turing machines are by Anthony Hay (CC0).
