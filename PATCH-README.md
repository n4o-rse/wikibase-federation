# PATCH-README

wikibase-federation 1.3.1: fixes `usecases/chublets/query_check.py` on Python 3.9. `Path.write_text(newline=...)` exists only from Python 3.10; the CI matrix tests 3.9 and 3.12, so every run since 1.3.0 failed on 3.9 (`test_the_endpoint_is_found_among_the_usual_paths_and_the_report_is_written`). The push itself is not affected.

## Contents

| Path | Status | Purpose |
|---|---|---|
| `usecases/chublets/query_check.py` | modified | reports are written with `open(..., newline="\n")` |
| `CHANGELOG.md`, `pyproject.toml`, `wbqs/__init__.py`, `CITATION.cff` | modified | version 1.3.1 |

Nothing generated is shipped. `PATCH-README.md` replaces the tracked one of 1.3.0.

## Applying

Unzip at the repository root (`C:\git\wikibase-federation`):

    tar -xf <path>\federation-1.3.1-patch.zip

## What to run

    python -m pytest -q
    ruff check .

## How to verify

1. **Tests** - `89 passed`, `All checks passed!`.
2. **CI** - the GitHub Actions run of the new commit is green for Python 3.9 and 3.12.
3. **Scope** - `git status --short` lists exactly the paths of the table and `PATCH-README.md`.

## Verified here

On a fresh clone with the 1.3.0 state plus this patch, with real Python 3.9.25 and 3.12: 89 passed and ruff clean on both. Before the fix the same suite failed on 3.9 with the `TypeError` above. The GitHub run itself was not seen.

## Commit

    git add PATCH-README.md CHANGELOG.md CITATION.cff pyproject.toml wbqs/__init__.py usecases/chublets/query_check.py

    git commit -m "1.3.1: Make query_check.py run on Python 3.9" -m "Path.write_text(newline=...) needs Python 3.10, the CI matrix also runs 3.9, so the tests of the query check failed there."

    git push

    git tag v1.3.1

    git push origin v1.3.1
