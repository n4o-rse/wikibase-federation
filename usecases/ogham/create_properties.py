#!/usr/bin/env python3
"""
Create (once) the local properties for the Ogham use case from model.py, record
their PIDs in usecases/ogham/properties.json, and set each ID property's
formatter URL (so external-id values resolve to a real IRI in the RDF/SPARQL).

Idempotent: existing entries in properties.json are reused; formatter URLs are
only added if not already present.

Run:
    python usecases\\ogham\\create_properties.py --dry-run   # show plan
    python usecases\\ogham\\create_properties.py             # create + set formatters
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


def _load_state() -> dict[str, str]:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict[str, str]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _ensure_formatter(client: WikibaseClient, prop_pid: str, formatter_pid: str, value: str) -> str:
    """Add the formatter-URL statement to a property, unless already present."""
    try:
        entity = client.get_entity(prop_pid)
    except ApiError:
        return "property not readable"
    for claim in entity.get("claims", {}).get(formatter_pid, []):
        existing = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if existing == value:
            return "exists"
    st = Statement(entity=prop_pid, prop=formatter_pid, prop_raw=formatter_pid,
                   value_raw=value, value_api=value, line_no=0, original="", value_datatype="string")
    client.create_claim(st)
    return "added"


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


def _create_or_reuse(client: WikibaseClient, p: dict) -> str:
    """Create a property, or reuse an existing one on a label conflict."""
    try:
        result = client.create_entity(
            new="property",
            labels={"en": p["label"]},
            descriptions={"en": p.get("description", "")},
            datatype=p["datatype"],
        )
        pid = result.get("entity", {}).get("id")
        print(f"  created {p['key']} -> {pid}")
        return pid
    except ApiError as exc:
        if "label-conflict" in (exc.detail or "") or "label-conflict" in str(exc):
            pid = client.find_property_by_label(p["label"])
            if pid:
                print(f"  reused existing {p['key']} -> {pid} (label conflict)")
                return pid
        raise


def ensure_properties(*, dry_run: bool = False) -> dict[str, str]:
    """Create missing local properties, set formatter URLs and equivalence maps."""
    state = _load_state()
    all_props = [model.EQUIV_PROPERTY, *model.LOCAL_PROPERTIES]
    to_create = [p for p in all_props if p["key"] not in state]
    with_formatter = [p for p in model.LOCAL_PROPERTIES if p.get("formatter")]
    with_equiv = [p for p in model.LOCAL_PROPERTIES if p.get("wd_equiv")]

    if to_create:
        print("Local properties to create:")
        for p in to_create:
            print(f"  {p['key']}: '{p['label']}' [{p['datatype']}]")
    else:
        print("All local properties already exist.")
    if with_formatter:
        print("Formatter URLs on: " + ", ".join(p["key"] for p in with_formatter))
    if with_equiv:
        print("Equivalence mappings on: " + ", ".join(p["key"] for p in with_equiv))

    if dry_run:
        print("Dry run: nothing created, no formatters/mappings set.")
        return state

    api_url, username, password, ua = _load_wikibase_config()
    client = WikibaseClient(api_url, username, password, user_agent=ua)
    print(f"Logging in as {username} ...")
    client.login()

    for p in to_create:
        pid = _create_or_reuse(client, p)
        if not pid:
            raise SystemExit(f"No id for {p['key']}")
        state[p["key"]] = pid
        _save_state(state)

    formatter_pid = state.get("formatter_url")
    if formatter_pid:
        for p in with_formatter:
            pid = state.get(p["key"])
            if pid:
                print(f"  formatter {p['key']} ({pid}): "
                      f"{_ensure_formatter(client, pid, formatter_pid, p['formatter'])}")

    equiv_pid = state.get(model.EQUIV_PROPERTY["key"])
    if equiv_pid:
        for p in with_equiv:
            pid = state.get(p["key"])
            if pid:
                print(f"  equiv {p['key']} ({pid}) = {p['wd_equiv']}: "
                      f"{_ensure_equiv(client, pid, equiv_pid, p['wd_equiv'])}")

    print(f"properties.json: {state}")
    return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create/ensure the Ogham local properties.")
    ap.add_argument("--dry-run", action="store_true", help="show plan; create nothing")
    args = ap.parse_args(argv)
    ensure_properties(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())