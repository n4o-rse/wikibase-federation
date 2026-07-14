#!/usr/bin/env python3
"""
Create (once) the subject items for the software use case from model.ITEMS, and
record their Q-ids in usecases/software/items.json. Idempotent: existing items
are reused.

Run:
    python usecases\\software\\create_items.py --dry-run
    python usecases\\software\\create_items.py
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

import model  # noqa: E402
from wbqs.client import DEFAULT_USER_AGENT, WikibaseClient  # noqa: E402

STATE_FILE = HERE / "items.json"


def _cfg() -> tuple[str, str, str, str]:
    for base in (Path.cwd(), REPO_ROOT):
        if (base / "config.ini").is_file():
            cp = configparser.ConfigParser()
            cp.read(base / "config.ini", encoding="utf-8")
            api = cp.get("wikibase", "api_url", fallback="").strip()
            user = os.environ.get("WIKIBASE_USERNAME") or cp.get("wikibase", "username", fallback="").strip()
            pw = os.environ.get("WIKIBASE_PASSWORD") or cp.get("wikibase", "password", fallback="")
            ua = cp.get("wikibase", "user_agent", fallback=DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
            if not api or not user or not pw or user == "YOUR_USERNAME":
                raise SystemExit("Missing api_url/username/password in config.ini (or env vars).")
            return api, user, pw, ua
    raise SystemExit("config.ini not found.")


def _load_state() -> dict[str, str]:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def ensure_items(*, dry_run: bool = False) -> dict[str, str]:
    """Return {item_key: QID}, creating missing subject items once."""
    state = _load_state()
    todo = [it for it in model.ITEMS if it.key not in state]

    if not todo:
        print(f"All subject items already exist: {state}")
        return state

    print("Subject items to create:")
    for it in todo:
        print(f"  {it.key}: {it.terms.get('labels', {}).get('en', '')}")
    if dry_run:
        print("Dry run: no items created.")
        return state

    api, user, pw, ua = _cfg()
    client = WikibaseClient(api, user, pw, user_agent=ua)
    print(f"Logging in as {user} ...")
    client.login()

    for it in todo:
        result = client.create_entity(
            new="item",
            labels=it.terms.get("labels"),
            descriptions=it.terms.get("descriptions"),
            aliases=it.terms.get("aliases"),
        )
        qid = result.get("entity", {}).get("id")
        if not qid:
            raise SystemExit(f"No id returned for {it.key}: {result}")
        state[it.key] = qid
        print(f"  created {it.key} -> {qid}")
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    print(f"items.json: {state}")
    return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create/ensure the software subject items.")
    ap.add_argument("--dry-run", action="store_true", help="show plan; create nothing")
    args = ap.parse_args(argv)
    ensure_items(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
