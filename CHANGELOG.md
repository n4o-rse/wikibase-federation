# Changelog

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
