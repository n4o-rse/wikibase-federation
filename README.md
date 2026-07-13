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
│   ├── client.py           #   Wikibase API client
│   ├── config.py           #   config + job / test-case resolution
│   └── importer.py         #   workflow (login, write, report)
├── testcases/              # one folder per test case …
│   └── example/
│       ├── input.qs        #   the QS data for that case
│       └── report/         #   reports for that case (created on demand, git-ignored)
└── tests/                  # parser unit tests
```

**Idea:** the code lives in the `wbqs/` package, the data in `testcases/`. A
pointer in `config.ini` selects which test case is imported. To add a new case,
create `testcases/my-case/input.qs` and set `testcase = testcases/my-case` in the
config.

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

**Not** supported: strings, dates, quantities, coordinates, qualifiers,
references, labels, descriptions, aliases. The focus is `wikibase-item`.

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

1. Put your data in `testcases/example/input.qs` — or create a new folder
   `testcases/<name>/input.qs` and point `testcase` at it in `config.ini`.

2. **Dry run** (writes nothing whilst `dry_run = true`):

   ```bash
   python main.py
   ```

3. **Go live**: set `dry_run = false` in `config.ini`, then run `python main.py`
   again.

Reports are written to `testcases/<name>/report/import_report_<timestamp>.json`.

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
testcase = testcases/example      ; folder holding the .qs file; reports -> <folder>/report
; qs_file = testcases/example/input.qs   ; alternatively a single file (takes precedence)

[import]
dry_run          = true
skip_existing    = true
maxlag           = 0
mark_bot         = false
throttle_seconds = 0.0
```

Relative paths are resolved **relative to `config.ini`**, so a run works
regardless of the current directory. Credentials may also be supplied via
environment variables (`WIKIBASE_USERNAME`, `WIKIBASE_PASSWORD`), which take
precedence and bypass INI `%` interpolation.

## Command-line options

```bash
python main.py testcases/example              # explicit test-case folder
python main.py testcases/example/input.qs     # a specific file
python main.py --dry-run                       # never write
python main.py --limit 1                       # only the first line (a good first test)
python main.py --federate-bare-qids            # treat bare Q-IDs as Wikidata items
python main.py --federate-bare-pids            # treat bare P-IDs as Wikidata properties
python main.py --no-skip-existing --verbose
```

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