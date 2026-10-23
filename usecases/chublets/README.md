# Use case: Chublets (push of the CSV model into chublets-wikibase.de)

Writes the data model and, step by step, the items of
[`chublets-wikibase-demo`](https://github.com/n4o-rse/chublets-wikibase-demo) into a real Wikibase.
The demo repository keeps everything as CSV and renders a static copy; this use case reads the same
`data/derived/entities/*.json` and writes it with `wbeditentity`. `wikibase-static` itself never gets
write access, and the credentials stay in the git-ignored `config.ini` here.

## Settings (same as the software use case on federated-objects.de)

- Every property is a **local** property. There are **no federated properties**.
- Item values may be **federated Wikidata items** (`http://www.wikidata.org/entity/Q...`). A Wikidata
  stub of the CSV (`origin = wikidata-stub`) is never created in the target; its P4 gives the
  federated value (`values = federated`, default). `values = local` creates the stubs as items instead.
- `url` properties are written as `string` (`url_as_string = true`, default).
- Dry run is the default. A real run needs `--write`, `allow_write = true` and an explicit `target`.

## Phases

| Phase | What | Ids in the target |
|---|---|---|
| `core` | Q1 to Q3, P1 to P10 | must equal the CSV ids, otherwise the run stops before the next write |
| `model` | the 7 classes and the 158 properties of `entities.csv` | new ids, recorded in `idmap-<target>.csv` |
| `items` | items of `entities.csv`, `--origin open-archaeo` / `wikidata`, `--limit N` | new ids, recorded in the idmap |

Default is `core,model`. Items follow later, in steps, as decided.

Each run finishes what earlier runs had to defer: a claim whose value points at an entity that is not in
the target yet is skipped, reported (`report/push-last.json`) and written by a later run.

## Files

| File | Role |
|---|---|
| `push.py` | the logic (source reading, translation, idempotent writing); no network of its own |
| `pipeline.py` | command line and `run()` for `main.py --pipeline` |
| `idmap-<target>.csv` | CSV id to target id (created by the first real run; commit it) |
| `state-<target>.json` | source claim id to target claim GUID (commit it) |
| `report/` | last report, git-ignored |

## Usage (Windows, from `C:\git\wikibase-federation`)

    copy config.example.ini config.ini

In `config.ini` set `[wikibase] api_url` (the `.../w/api.php` of chublets-wikibase.de), a bot password,
`[chublets] source_dir` (default `..\chublets-wikibase-demo`) and `target = chublets-wikibase.de`.

    python usecases\chublets\pipeline.py --probe
    python usecases\chublets\pipeline.py
    python usecases\chublets\pipeline.py --write

`--probe` logs in, prints the generator, the extensions and whether Q1 to Q3 and P1 to P10 are free (or
already right). It writes nothing. The plain call is the dry run and prints the list of calls; ids marked
`(predicted)` are what the target is expected to hand out.

Later steps:

    python usecases\chublets\pipeline.py --write --phase items --origin open-archaeo --limit 20
    python usecases\chublets\pipeline.py --write --phase items --origin wikidata

## Not covered

- `wbeditentity` with federated values is alpha (see the main README); the first real run on the target is
  the first real test. Answers of the target (`--probe`, one `wbgetentities`) are still to be saved as fixtures.
- The ids of items and properties from 100 on differ between the CSV and the target. `idmap-<target>.csv`
  holds the mapping; writing it back into the CSV is a step of `wikibase-static`, not of this repository.
- A crash between creating an entity and writing its idmap line would leave an entity the idmap does not
  know. The idmap is written line by line right after each creation to keep that window small.
- Quantities with a unit and entities of another kind of reference are deferred, not translated.
