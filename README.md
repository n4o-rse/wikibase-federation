# Wikibase QuickStatements API Importer

A small, robust tool for writing QuickStatements-style **item statements** into a
Wikibase instance through the Wikibase / MediaWiki Action API — including
**federated Wikidata properties and items**.

## Project layout

```
wikibase-federation/
├── main.py                 # entry point (run this)
├── config.ini              # your configuration (git-ignored) – from config.example.ini
├── config.example.ini      # template
├── requirements.txt        # all dependencies (runtime + dev tools)
├── wbqs/                    # the package code
│   ├── parser.py           #   QS parsing (network-free, unit-tested)
│   ├── client.py           #   Wikibase API client (retries, entity/property creation)
│   ├── config.py           #   config + job resolution
│   └── importer.py         #   workflow (login, write, report)
├── usecases/               # one folder per use case (data + build scripts)
│   ├── ogham/              #   Ogham stone across several Wikibases
│   └── software/           #   research software with a CodeMeta crosswalk
└── tests/                  # parser unit tests
```

**Idea:** the reusable code lives in `wbqs/`, each use case in `usecases/<name>/`.
A pointer in `config.ini` (`job_dir = usecases/<name>`) selects the active one.
A use case is driven by a frozen `model.py` (the single source of truth) and a
small `pipeline.py` that creates items/properties, generates `input.qs`, and
imports — all in one `python main.py` (see *Use cases & pipeline* below).

## Why the API and not QuickStatements?

The goal is Wikibase's **ontology federation**, in two flavours:

- **Federated values** – a local property with a *Wikidata item* as its value.
- **Federated properties** – the *property itself* comes from Wikidata.

The API representation of federated entities is still alpha, which is why
QuickStatements does not (yet) handle it. A direct `wbcreateclaim` call using the
full entity URI does work — both as the value (`id`) and, for federated
properties, as the `property` parameter:

```json
{ "property": "http://www.wikidata.org/entity/P5572",
  "value":    {"entity-type": "item", "id": "http://www.wikidata.org/entity/Q5"} }
```

## Use cases & pipeline

Beyond plain `.qs` import, a use case can drive the whole flow from a frozen
`model.py`. With `[run] pipeline = true` (or `--pipeline`), `main.py` delegates to
the job folder's `pipeline.py`, which runs in order:

1. **ensure item(s)** — create the subject item(s) once (idempotent, recorded in
   `hub_item.json` / `items.json`);
2. **ensure properties** — create the local properties once (idempotent,
   recorded in `properties.json`), set formatter URLs / equivalence mappings, and
   reuse existing properties on a label conflict;
3. **build `input.qs`** — regenerate it from `model.py`;
4. **import** — write the statements (and, for Ogham, apply references).

Everything is idempotent and dry-run-safe: re-running skips what already exists.

Two use cases ship as worked examples:

- **`usecases/ogham/`** — one Ogham stone (CIIC 81) as a *hub* item linking to the
  same object in several other Wikibases (FactGrid, Fuzzy-SL, Semantic Kompakkt,
  SquirrelBase, LinkedOgham) plus native Wikidata values. Demonstrates
  *statements about an entity that lives in another Wikibase*.
- **`usecases/software/`** — two research-software items modelled with a
  **CodeMeta ↔ Wikidata crosswalk**: reuse Wikidata's ontology where it fits, add
  local properties for the CodeMeta-specific fields it lacks. Demonstrates
  *reference-source / ontology reuse plus a domain extension*.

Two switches in each `model.py`:

- `PROPERTY_MODE` — `"federated"` (predicate = `wd:P…`), `"local"` (a local
  property, works without the Federated Properties feature), or `"local+federated"`
  (both, side by side, for the comparison). Local equivalents record their
  Wikidata property via a string `equivalent Wikidata property`.
- `USE_FEDERATED_VALUES` — item values as federated `wd:Q…` (default) or as
  external-id "Wikidata ID" literals (fully federation-free).

## Input format

Three columns (tab- or whitespace-separated): `<subject> <property> <value>`.
Blank lines and lines starting with `#` are ignored.

- **Subject**: always a **local** item (`Q…`).
- **Property**: local (`P…`) **or** federated (`wd:P…` or a Wikidata URI).
- **Value**: a local item (`Q…`) **or** federated (`wd:Q…` or a Wikidata URI).

All four combinations are supported:

```text
Q3  P1        Q4        # local property    + local item value
Q3  P1        wd:Q5     # local property    + federated item value
Q3  wd:P5572  Q4        # federated property + local item value
Q3  wd:P5572  wd:Q5     # federated property + federated item value
```

Federated references are normalised to the entity URI
(`http://www.wikidata.org/entity/…`). For properties, `wd:P…`, `wdt:P…`,
`…/entity/P…` and `…/prop/direct/P…` are all accepted.

An optional **4th column** carries a datatype hint for non-item values:

```text
Q5  wd:P2888  https://database.factgrid.de/entity/Q1000294   url
Q5  P6        gares_1                                         external-id
Q5  wd:P625   51.893659,-8.492443                            coordinate
Q5  wd:P1684  CASSITTAS MAQI MUCOI CALLITI                    monolingual@mul
```

Supported value kinds: `item` (default), `url`, `string`, `external-id`,
`coordinate` (`lat,lon`) and `monolingual@<lang>`. Qualifiers are still applied
in a separate step; references are added by the use-case pipeline.

## Requirements

- Python 3.9 or newer.
- A target Wikibase with ontology federation enabled: for federated values, a
  `wikibase-item` property that permits federated values; for federated
  properties, property federation must be switched on.
- A **bot password** (`Special:BotPasswords`); the username is then
  `MainAccount@botname`.

## Setup (simple, global install)

No virtual environment needed — install the dependencies globally and run.

1. Install Python 3.9+ (on Windows, tick "Add Python to PATH" during setup).

2. Download or clone this project, then open a terminal in the project folder.

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   If `pip` is not found on Windows, use `py -m pip install -r requirements.txt`.

4. Create your configuration from the template and edit it:

   ```bash
   # Windows (PowerShell):
   copy config.example.ini config.ini
   # Linux/macOS:
   cp config.example.ini config.ini
   ```

   Then open `config.ini` and fill in `api_url`, `username` (`Account@bot`),
   `password` and `user_agent`.

That's it — you are ready to run.

> Optional: if you prefer an isolated environment, run
> `python -m venv .venv` and activate it before step 3
> (`.\.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate`
> elsewhere). It is not required.

## Running

1. Point `config.ini` at a use case: `job_dir = usecases/ogham` (or
   `usecases/software`), and set `[run] pipeline = true`.

2. **Dry run** (writes nothing whilst `dry_run = true`):

   ```bash
   python main.py
   ```

3. **Go live**: set `dry_run = false` in `config.ini`, then run `python main.py`
   again. For a first cautious run use `[run] limit = 1` (or `--limit 1`).

Reports are written to `usecases/<name>/report/import_report_<timestamp>.json`.

### In VS Code

`main.py` runs **with no arguments**, so you can start it with the play button
(top right) or right-click → **"Run Python File in Terminal"**. The job is taken
from `config.ini`. If `config.ini` is missing, `config.example.ini` is used and a
**forced dry run** is performed. Under **Run and Debug** (F5) there are three
launches: a dry run of the config job, a live run of the config job, and a run of
the **currently open** `.qs` file (dry run, `--limit 1`).

## `config.ini` reference

```ini
[wikibase]
api_url    = https://federated-objects.de/w/api.php
username   = Fthierygeo@importbot
password   = YOUR_BOT_PASSWORD
user_agent = wikibase-qs-api-importer/1.1 (you@example.org)

[job]
job_dir = usecases/ogham         ; folder holding model.py / input.qs; reports -> <folder>/report
; qs_file = usecases/ogham/input.qs     ; alternatively a single file (takes precedence)

[import]
dry_run          = true
skip_existing    = true
maxlag           = 0
mark_bot         = false
throttle_seconds = 0.0

[run]
pipeline           = true    ; run the job folder's pipeline.py (create -> build -> import)
limit              = 0       ; only the first N statements (0 = all)
federate_bare_qids = false
federate_bare_pids = false
verbose            = false
```

Relative paths are resolved **relative to `config.ini`**, so a run works
regardless of the current directory. Credentials may also be supplied via
environment variables (`WIKIBASE_USERNAME`, `WIKIBASE_PASSWORD`), which take
precedence and bypass INI `%` interpolation.

## Command-line options

```bash
python main.py                                 # runs the [job]; pipeline if [run] pipeline = true
python main.py --pipeline                       # force the job folder's pipeline.py
python main.py --no-pipeline                    # force a plain .qs import instead
python main.py usecases/ogham                   # explicit job folder
python main.py --dry-run                         # never write
python main.py --limit 1                         # only the first line (a good first test)
python main.py --federate-bare-qids              # treat bare Q-IDs as Wikidata items
python main.py --federate-bare-pids              # treat bare P-IDs as Wikidata properties
python main.py --no-skip-existing --verbose
```

CLI flags override the `[run]` defaults in `config.ini`.

## Behaviour & safety nets

- **Duplicate check** (`skip_existing`): a statement whose property and value
  already exist is skipped.
- **User-Agent**, **`assert=user`**, optional **`maxlag`**, **`badtoken`
  refresh**, **GET retries** and **throttling** are built in.
- **Report** per run inside the test case's `report/` folder.
- **Exit codes**: `0` = success, `1` = at least one write error, `2` = parsing /
  configuration error.

Two assumptions for federated properties (if your instance differs you will see a
clear API error, or a duplicate that is not recognised): the `property` parameter
receives the entity URI, and `skip_existing` relies on `wbgetentities` returning
the claim under that same URI key.

## Security

- Never commit `config.ini` (it is in `.gitignore`).
- Prefer **bot passwords** (they consist only of letters and digits).
- **Revoke any password that has ever been visible in a chat or script.**

## Development

Tests and linting use the same `requirements.txt`:

```bash
pip install -r requirements.txt
pytest -q
ruff check .
```

An optional editable install provides the `wb-qs-import` command:

```bash
pip install -e .
wb-qs-import --dry-run
```

## Licence

MIT — see `LICENSE` (add your name to the copyright line).