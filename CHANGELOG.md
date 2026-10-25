# Changelog

## 1.2.4
- Documentation only: result of the Chublets push (980 entities, 7 012 statements, second run 0 writes), federated values
  confirmed on the target, the idmap is published by `wikibase-static` 0.19.0, the push account has no `bot` right.

## 1.2.3
- Chublets push: Wikibase allows at most 250 characters in a label, description or alias. Longer texts are cut at a
  word boundary and end with an ellipsis (`shorten`); the report lists them under `shortened`, the source
  stays whole. The first batch of items had three descriptions that the wiki refused (Q150, Q281, Q289 of the CSV);
  22 of the 796 open-archaeo items are affected.
- Tests: 2 more (71 in the repository); the fake wiki refuses texts over 250 characters.

## 1.2.2
- Chublets push: when the wiki rate-limits the account ("Anti-Missbrauchs-Maßnahme", `ratelimited`) the push
  waits `rate_limit_wait` seconds and retries (`rate_limit_retries` times), then stops with a clear message;
  idmap and state are already saved, a rerun continues. `throttle_seconds` defaults to 1 for this use case.
  The first real run created 90 entities before the limit hit.
- Lint: `E501` is ignored for the chublets files (long messages and fixtures).
- Tests: 3 more (69 in the repository).

## 1.2.1
- Chublets use case: `--inventory` (read only list of the target), `adopt-<target>.csv` (map CSV entities
  onto entities that already exist on the target, checked by label and datatype before any write) and
  `core_ids = any` (the core no longer has to get the ids of the CSV). `--probe` checks the adopt file.
- `WikibaseClient`: new `entity_namespaces` and `list_titles`.
- Tests: 10 more in `tests/test_chublets_push.py` (26 there, 65 in the repository).

## 1.2.0
- New use case `usecases/chublets/` (S7g of wikibase-static): pushes the CSV model of
  `chublets-wikibase-demo` into a real Wikibase with `wbeditentity`. Phases `core`, `model`, `items`;
  local properties only, federated Wikidata items as values, `url` as `string`; dry run by default;
  `idmap-<target>.csv` and `state-<target>.json` make reruns idempotent.
- `WikibaseClient`: new `edit_entity` (complete Wikibase JSON, create or add claims), `get_entities`
  (batched, missing ids map to `None`) and `siteinfo`.
- `config.example.ini`: new `[chublets]` section.
- Tests: `tests/test_chublets_push.py` (16 tests against a fake API).

## 1.1.0
- Restructured into a `wbqs/` package (parser, client, config, importer) with a
  thin `main.py` entry point.
- New `[job]` config section: point `testcase` at a folder (self-contained data +
  report/) or `qs_file` at a single file. Relative paths resolve next to config.ini.
- Reports now land in the test case's own `report/` folder.
- CLI accepts a .qs file or test-case folder as an override; added
  `--federate-bare-pids`.


## 1.0.0
- Federated Wikidata *properties*: property column now accepts wd:P... / a
  Wikidata property URI (normalised to the entity URI), enabling all four
  local/federated combinations of property and value.
- Configurable I/O dirs: inputs from data_dir (default /root/data), reports
  to report_dir (default /root/report); auto-pick single .qs in data_dir.
- Zero-argument run support (VS Code context menu / play button): auto-detects
  config.ini and input file, falls back to config.example.ini in dry-run.
- Shipped .vscode/ launch, settings and extension recommendations.
- Reworked from the original ChatGPT-generated script.
- Added descriptive User-Agent header (MediaWiki API etiquette).
- Added API-level error detection for login / token / entity reads.
- Added `assert=user`, optional `maxlag`, `badtoken` token refresh, throttling,
  and GET-only network retries.
- Entity cache with invalidation after a successful write.
- Credentials can come from environment variables.
- Timestamped, git-ignored import reports (fixes previous `.gitignore` mismatch).
- Split pure parsing into `qs_parser.py` and added unit tests + CI.
