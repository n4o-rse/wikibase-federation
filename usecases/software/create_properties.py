#!/usr/bin/env python3
"""
Create (once) the local properties for the software use case from model.py, and
record their PIDs in usecases/software/properties.json. Also creates the meta
property 'equivalent Wikidata property' (string) and, for each local property
that has a Wikidata equivalent, sets `equivalent Wikidata property = P<nn>` on
the property itself (this is the local<->Wikidata mapping; we use a string
property because equivalent property (P1628) is url datatype and url is blocked).

Idempotent: existing entries in properties.json are reused; the equivalence
statement is only added if not already present.

Run:
    python usecases\\software\\create_properties.py --dry-run
    python usecases\\software\\create_properties.py
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
from wbqs.client import ApiError, DEFAULT_USER_AGENT, WikibaseClient  # noqa: E402
from wbqs.parser import Statement  # noqa: E402

STATE_FILE = HERE / "properties.json"


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


def _save(state: dict[str, str]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _ensure_equiv(client: WikibaseClient, prop_pid: str, equiv_pid: str, value: str) -> str:
    """Set 'equivalent Wikidata property = <value>' on a property, if not present."""
    try:
        entity = client.get_entity(prop_pid)
    except ApiError:
        return "not readable"
    for claim in entity.get("claims", {}).get(equiv_pid, []):
        if claim.get("mainsnak", {}).get("datavalue", {}).get("value") == value:
            return "exists"
    st = Statement(entity=prop_pid, prop=equiv_pid, prop_raw=equiv_pid,
                   value_raw=value, value_api=value, line_no=0, original="", value_datatype="string")
    client.create_claim(st)
    return "added"


def ensure_properties(*, dry_run: bool = False) -> dict[str, str]:
    """Create the local + meta properties and set the equivalence mappings."""
    state = _load_state()
    all_props = [model.EQUIV_PROPERTY, *model.LOCAL_PROPERTIES]
    todo = [p for p in all_props if p["key"] not in state]
    with_equiv = [p for p in model.LOCAL_PROPERTIES if p.get("wd_equiv")]

    if todo:
        print("Local properties to create:")
        for p in todo:
            print(f"  {p['key']}: '{p['label']}' [{p['datatype']}]")
    else:
        print("All local properties already exist.")
    print("Equivalence mappings to ensure on: " + ", ".join(p["key"] for p in with_equiv))

    if dry_run:
        print("Dry run: nothing created, no mappings set.")
        return state

    api, user, pw, ua = _cfg()
    client = WikibaseClient(api, user, pw, user_agent=ua)
    print(f"Logging in as {user} ...")
    client.login()

    for p in todo:
        pid = None
        try:
            result = client.create_entity(
                new="property",
                labels={"en": p["label"]},
                descriptions={"en": p.get("description", "")},
                datatype=p["datatype"],
            )
            pid = result.get("entity", {}).get("id")
            print(f"  created {p['key']} -> {pid}")
        except ApiError as exc:
            # A property with this label already exists -> reuse it.
            if "label-conflict" in (exc.detail or "") or "label-conflict" in str(exc):
                pid = client.find_property_by_label(p["label"])
                if not pid:
                    raise
                print(f"  reused existing {p['key']} -> {pid} (label conflict)")
            else:
                raise
        if not pid:
            raise SystemExit(f"No id for {p['key']}: creation failed")
        state[p["key"]] = pid
        _save(state)

    equiv_pid = state.get(model.EQUIV_PROPERTY["key"])
    if equiv_pid:
        for p in with_equiv:
            pid = state.get(p["key"])
            if pid:
                status = _ensure_equiv(client, pid, equiv_pid, p["wd_equiv"])
                print(f"  equiv {p['key']} ({pid}) = {p['wd_equiv']}: {status}")

    print(f"properties.json: {state}")
    return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create/ensure the software local properties.")
    ap.add_argument("--dry-run", action="store_true", help="show plan; create nothing")
    args = ap.parse_args(argv)
    ensure_properties(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())