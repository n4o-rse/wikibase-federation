#!/usr/bin/env python3
"""
One-run pipeline for the Ogham use case:

    1. ensure the hub item exists (create once, idempotent, dry-run-safe)
    2. regenerate input.qs from model.py
    3. import the statements

Invoked by main.py via `--pipeline`, or standalone:

    python usecases\\ogham\\pipeline.py            # honours config.ini dry_run
    python usecases\\ogham\\pipeline.py --dry-run  # preview end-to-end, writes nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

import apply_references  # noqa: E402
import build_qs  # noqa: E402
import create_item  # noqa: E402
import create_properties  # noqa: E402
import model  # noqa: E402
from wbqs.config import ConfigError, load, resolve_config_path  # noqa: E402
from wbqs.importer import run as import_run  # noqa: E402


def run(*, config_path: Path | None = None, dry_run: bool = False, limit: int | None = None) -> int:
    print("=== Ogham pipeline ===")

    # 1. ensure the hub item (idempotent).
    print("[1/5] ensure hub item")
    qid = create_item.ensure_hub_item(dry_run=dry_run)
    if qid:
        model.HUB_ITEM = qid  # keep in-memory value current for build_qs

    # 2. ensure the local properties (idempotent).
    print("[2/5] ensure local properties")
    create_properties.ensure_properties(dry_run=dry_run)

    # 3. regenerate the QS file.
    print("[3/5] build input.qs")
    build_qs.main([])

    # 4. import.
    print("[4/5] import")
    if config_path is None:
        config_path, _ = resolve_config_path(None)
    try:
        app = load(Path(config_path), cli_dry_run=dry_run)
    except ConfigError as exc:
        print(f"config error: {exc}")
        return 2
    rc = import_run(app, limit=limit)

    # 5. apply provenance references (needs the claims to exist).
    print("[5/5] apply references")
    if limit is not None:
        print("  (skipped: --limit set, some claims may be missing)")
    else:
        apply_references.ensure_references(dry_run=dry_run)
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the full Ogham pipeline.")
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