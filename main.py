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
import importlib.util
import logging
from pathlib import Path

from wbqs import __version__
from wbqs.config import ConfigError, load, read_config, resolve_config_path, resolve_job_dir
from wbqs.importer import run


def _load_pipeline_module(job_dir: Path):
    p = job_dir / "pipeline.py"
    if not p.is_file():
        return None
    spec = importlib.util.spec_from_file_location("job_pipeline", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    p.add_argument("--pipeline", action="store_true",
                   help="Run the job folder's pipeline.py (overrides [run] pipeline).")
    p.add_argument("--no-pipeline", action="store_true",
                   help="Force plain import even if [run] pipeline = true.")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose (DEBUG) logging.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Read config once for [run] defaults (tolerate a missing config).
    cfg = None
    cfg_path = None
    try:
        cfg_path, _ = resolve_config_path(args.config)
        cfg = read_config(cfg_path)
    except ConfigError:
        pass

    def cfg_bool(section: str, key: str, default: bool = False) -> bool:
        return cfg.getboolean(section, key, fallback=default) if cfg else default

    # Merge CLI flags with [run] defaults; explicit CLI wins.
    verbose = args.verbose or cfg_bool("run", "verbose")
    limit = args.limit if args.limit is not None else (
        cfg.getint("run", "limit", fallback=0) if cfg else 0) or None
    federate_bare_qids = args.federate_bare_qids or cfg_bool("run", "federate_bare_qids")
    federate_bare_pids = args.federate_bare_pids or cfg_bool("run", "federate_bare_pids")

    pipeline_mode = (args.pipeline or cfg_bool("run", "pipeline")) and not args.no_pipeline

    # Effective dry-run: CLI --dry-run OR config [import] dry_run. Used so the
    # pipeline's item creation also honours a config-level dry run.
    effective_dry_run = args.dry_run or cfg_bool("import", "dry_run")

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("wb-qs-import")

    if pipeline_mode:
        if cfg is None or cfg_path is None:
            log.error("Pipeline requested but no config.ini found.")
            return 2
        try:
            job_dir = resolve_job_dir(cfg, cfg_path.resolve().parent, args.target)
        except ConfigError as exc:
            log.error("%s", exc)
            return 2
        pipeline = _load_pipeline_module(job_dir)
        if pipeline is None:
            log.error("No pipeline.py found in %s", job_dir)
            return 2
        return pipeline.run(config_path=cfg_path, dry_run=effective_dry_run, limit=limit)

    try:
        app = load(
            args.config,
            args.target,
            cli_dry_run=args.dry_run,
            cli_no_skip_existing=args.no_skip_existing,
        )
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    return run(
        app,
        limit=limit,
        federate_bare_qids=federate_bare_qids,
        federate_bare_pids=federate_bare_pids,
    )


if __name__ == "__main__":
    raise SystemExit(main())