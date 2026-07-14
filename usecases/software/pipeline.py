#!/usr/bin/env python3
"""
One-run pipeline for the software use case:

    1. ensure the subject items exist (idempotent)
    2. ensure the local properties + equivalence mappings (idempotent)
    3. regenerate input.qs from model.py
    4. import

Invoked by main.py via `--pipeline` (or [run] pipeline = true), or standalone:
    python usecases\\software\\pipeline.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

import build_qs  # noqa: E402
import create_items  # noqa: E402
import create_properties  # noqa: E402
from wbqs.config import ConfigError, load, resolve_config_path  # noqa: E402
from wbqs.importer import run as import_run  # noqa: E402


def run(*, config_path: Path | None = None, dry_run: bool = False, limit: int | None = None) -> int:
    print("=== Software pipeline ===")
    print("[1/4] ensure subject items")
    create_items.ensure_items(dry_run=dry_run)
    print("[2/4] ensure local properties + mappings")
    create_properties.ensure_properties(dry_run=dry_run)
    print("[3/4] build input.qs")
    build_qs.main([])
    print("[4/4] import")
    if config_path is None:
        config_path, _ = resolve_config_path(None)
    try:
        app = load(Path(config_path), cli_dry_run=dry_run)
    except ConfigError as exc:
        print(f"config error: {exc}")
        return 2
    return import_run(app, limit=limit)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the full software pipeline.")
    ap.add_argument("--dry-run", action="store_true", help="preview end-to-end; write nothing")
    ap.add_argument("--limit", type=int, default=None, help="only import the first N statements")
    args = ap.parse_args(argv)
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    return run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
