#!/usr/bin/env python3
"""
Create (once) a fresh hub item for the Ogham use case, with label / alias /
description from model.py, and remember its Q-id so it is never re-created.

Idempotent: the created Q-id is stored in usecases/ogham/hub_item.json. On later
runs the existing item is reused. model.py's HUB_ITEM is kept in sync so
build_qs.py uses the right item.

Run (Windows / VS Code, global Python):
    python usecases\\ogham\\create_item.py --dry-run   # show plan, create nothing
    python usecases\\ogham\\create_item.py             # create once (or reuse)
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

import model  # noqa: E402
from wbqs.client import DEFAULT_USER_AGENT, WikibaseClient  # noqa: E402

STATE_FILE = HERE / "hub_item.json"


def _load_wikibase_config() -> tuple[str, str, str, str]:
    cfg_path = None
    for base in (Path.cwd(), REPO_ROOT):
        if (base / "config.ini").is_file():
            cfg_path = base / "config.ini"
            break
    if cfg_path is None:
        raise SystemExit("config.ini not found (looked in cwd and repo root).")
    cp = configparser.ConfigParser()
    cp.read(cfg_path, encoding="utf-8")
    api_url = cp.get("wikibase", "api_url", fallback="").strip()
    username = os.environ.get("WIKIBASE_USERNAME") or cp.get("wikibase", "username", fallback="").strip()
    password = os.environ.get("WIKIBASE_PASSWORD") or cp.get("wikibase", "password", fallback="")
    ua = cp.get("wikibase", "user_agent", fallback=DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
    if not api_url or not username or not password or username == "YOUR_USERNAME":
        raise SystemExit("Missing api_url/username/password in config.ini (or env vars).")
    return api_url, username, password, ua


def _sync_model_hub_item(qid: str) -> None:
    path = HERE / "model.py"
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(r'^HUB_ITEM = "[^"]*"',
                          f'HUB_ITEM = "{qid}"', text, count=1, flags=re.MULTILINE)
    if n == 1 and new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f'  model.py updated: HUB_ITEM = "{qid}"')


def _recorded_qid() -> str | None:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("qid")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def ensure_hub_item(*, dry_run: bool = False) -> str | None:
    """Return the hub item Q-id, creating it once if needed.

    Idempotent via hub_item.json. In dry-run, never creates; returns the recorded
    id if present, else None (caller previews against model.HUB_ITEM).
    """
    existing = _recorded_qid()
    if existing:
        print(f"Hub item already exists: {existing} (from hub_item.json)")
        _sync_model_hub_item(existing)
        return existing

    labels = model.TERMS.get("labels", {})
    descriptions = model.TERMS.get("descriptions", {})
    aliases = model.TERMS.get("aliases", {})
    print("Hub item not created yet. Planned terms:")
    print(f"  label:       {labels}")
    print(f"  description: {descriptions}")
    print(f"  aliases:     {aliases}")

    if dry_run:
        print("Dry run: item would be created here (nothing written).")
        return None

    api_url, username, password, ua = _load_wikibase_config()
    client = WikibaseClient(api_url, username, password, user_agent=ua)
    print(f"Logging in as {username} ...")
    client.login()
    result = client.create_entity(new="item", labels=labels, descriptions=descriptions, aliases=aliases)
    qid = result.get("entity", {}).get("id")
    if not qid:
        raise SystemExit(f"No id returned: {result}")

    STATE_FILE.write_text(json.dumps({"qid": qid}, indent=2), encoding="utf-8")
    print(f"Created new item: {qid}  (recorded in hub_item.json)")
    _sync_model_hub_item(qid)
    return qid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create/ensure the Ogham hub item.")
    ap.add_argument("--dry-run", action="store_true", help="show plan; create nothing")
    args = ap.parse_args(argv)
    ensure_hub_item(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())