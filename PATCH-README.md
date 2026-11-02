# PATCH-README

wikibase-federation 1.3.0: the Chublets push can remove claims that left the source (`--prune`), and a read-only script checks how the pushed data looks in the query service of chublets-wikibase.de. Needed after the data care of 2026-11-02 in chublets-wikibase-demo (22 items no longer chublets, 2 duplicate developers of Alligator removed, 6 statements re-added with a reference).

## Contents

| Path | Status | Purpose |
|---|---|---|
| `usecases/chublets/push.py` | modified | `Pusher.stale_claims()`, `Pusher.prune()`, `--prune` handling in `run()`; stale remote claims no longer count as "already present" |
| `usecases/chublets/pipeline.py` | modified | CLI `--prune`, `--prune-max` (default 50), summary line |
| `usecases/chublets/query_check.py` | new | read-only check of the query service (Task: how federated values appear on Q811) |
| `usecases/chublets/README.md` | modified | sections on `--prune` and the query check |
| `tests/test_chublets_push.py` | modified | fake wiki knows `wbremoveclaims`; 11 prune tests |
| `tests/test_chublets_query_check.py` | new | 7 tests against a local fake SPARQL server |
| `CHANGELOG.md`, `pyproject.toml`, `wbqs/__init__.py`, `CITATION.cff` | modified | version 1.3.0, date-released 2026-11-02 |

Nothing generated is shipped. `PATCH-README.md` replaces the tracked one of 1.2.4.

## Applying

Unzip at the repository root (`C:\git\wikibase-federation`):

    tar -xf <path>\federation-1.3.0-patch.zip

Overwritten files: the modified ones above (diverged local copies would have to be merged by hand).

## What to run

    python -m pytest -q
    ruff check .

The live steps (`--prune`, `query_check.py`) are in the step-by-step guide; they write to chublets-wikibase.de resp. `usecases/chublets/report/` and need your credentials / network.

## How to verify

1. **Tests** - `python -m pytest -q` -> `89 passed`.
2. **Lint** - `ruff check .` -> `All checks passed!`.
3. **Nothing else changed** - `git status --short` lists exactly the paths of the table (and `PATCH-README.md`).

## Verified here

Applied to a fresh clone of the 1.2.4 state (cba23f7): 89 passed, ruff clean. NOT verified: any call against chublets-wikibase.de or its query service (the sandbox cannot reach the host); `--prune` is tested against a fake wiki only, `query_check.py` against a local fake SPARQL server only. The live endpoint path of the query service is a guess among three usual ones; pass `--endpoint` if none answers.

## Commit

    git add PATCH-README.md CHANGELOG.md CITATION.cff pyproject.toml wbqs/__init__.py usecases/chublets/push.py usecases/chublets/pipeline.py usecases/chublets/query_check.py usecases/chublets/README.md tests/test_chublets_push.py tests/test_chublets_query_check.py

    git commit -m "1.3.0: Prune claims that left the source, check the query service" -m "A statement removed from the CSV model stayed on the wiki, so the live data drifted from the source. --prune removes claims the push wrote earlier and the source no longer holds, with a dry run and a limit." -m "query_check.py reads how federated values appear in the query service."

    git push
