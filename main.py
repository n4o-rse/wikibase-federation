#!/usr/bin/env python3
"""Entry point: run a QuickStatements-to-Wikibase import job.

Runs with no arguments (VS Code "Run Python File"): the job is taken from
config.ini ([job] testcase / qs_file). You may also pass a .qs file or a
test-case folder to override the config.

Examples:
    python main.py
    python main.py testcases/example
    python main.py testcases/example/input.qs --dry-run --limit 1
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from wbqs import __version__
from wbqs.config import ConfigError, load
from wbqs.importer import run


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Import QuickStatements item triples into a Wikibase via the API.",
    )
    p.add_argument("target", type=Path, nargs="?", default=None,
                   help="Optional .qs file or test-case folder (overrides [job] in config).")
    p.add_argument("--config", type=Path, default=None, help="Path to config.ini (auto-detected if omitted).")
    p.add_argument("--dry-run", action="store_true", help="Parse and print only; do not write.")
    p.add_argument("--no-skip-existing", action="store_true", help="Do not check for duplicate claims.")
    p.add_argument("--federate-bare-qids", action="store_true",
                   help="Treat bare value Q-IDs as Wikidata items.")
    p.add_argument("--federate-bare-pids", action="store_true",
                   help="Treat bare properties as Wikidata properties.")
    p.add_argument("--limit", type=int, default=None, help="Only process the first N statements.")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose (DEBUG) logging.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        app = load(
            args.config,
            args.target,
            cli_dry_run=args.dry_run,
            cli_no_skip_existing=args.no_skip_existing,
        )
    except ConfigError as exc:
        logging.getLogger("wb-qs-import").error("%s", exc)
        return 2

    return run(
        app,
        limit=args.limit,
        federate_bare_qids=args.federate_bare_qids,
        federate_bare_pids=args.federate_bare_pids,
    )


if __name__ == "__main__":
    raise SystemExit(main())
