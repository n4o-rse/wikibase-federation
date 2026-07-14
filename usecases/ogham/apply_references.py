#!/usr/bin/env python3
"""
Add provenance references to the materialised statements (coordinate #7,
inscription #8) on the hub item, driven by model.STATEMENTS[*].references.

Because the url datatype (wd:P854 reference URL) is blocked on this instance,
references use external-id snaks (e.g. @factgrid_id = Q1000294) that resolve to
the source Wikibase via the property's formatter URL.

Idempotent: a reference is only added if an equivalent one is not already there.
Run after the import step (the claims must exist first).
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
from wbqs.parser import parse_property  # noqa: E402

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
            return api, user, pw, ua
    raise SystemExit("config.ini not found.")


def _resolve_prop(token: str, pid_map: dict[str, str]) -> str | None:
    if token.startswith("@"):
        return pid_map.get(token[1:])
    return parse_property(token)


def _build_snaks(refs: list, pid_map: dict[str, str]) -> dict:
    snaks: dict[str, list] = {}
    for token, _kind, value in refs:
        pid = _resolve_prop(token, pid_map)
        if not pid:
            continue
        snaks.setdefault(pid, []).append({
            "snaktype": "value",
            "property": pid,
            "datavalue": {"value": value, "type": "string"},
        })
    return snaks


def _has_reference(claim: dict, snaks: dict) -> bool:
    for ref in claim.get("references", []):
        rsnaks = ref.get("snaks", {})
        if all(
            any(s.get("datavalue", {}).get("value") == want[0]["datavalue"]["value"]
                for s in rsnaks.get(pid, []))
            for pid, want in snaks.items()
        ):
            return True
    return False


def ensure_references(*, dry_run: bool = False) -> None:
    pid_map = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.is_file() else {}
    to_do = [st for st in model.STATEMENTS if getattr(st, "references", None)]
    if not to_do:
        print("No references defined.")
        return

    print(f"References to ensure: {len(to_do)}")
    if dry_run:
        for st in to_do:
            print(f"  #{st.n} {st.prop}: {st.references}  (dry run, not applied)")
        return

    api, user, pw, ua = _cfg()
    client = WikibaseClient(api, user, pw, user_agent=ua)
    client.login()

    for st in to_do:
        main_prop = _resolve_prop(st.prop, pid_map)
        snaks = _build_snaks(st.references, pid_map)
        if not snaks:
            print(f"  #{st.n}: could not resolve reference property; skipped")
            continue
        entity = client.get_entity(model.HUB_ITEM)
        claims = entity.get("claims", {}).get(main_prop, [])
        if not claims:
            print(f"  #{st.n}: no claim on {main_prop}; run the import first")
            continue
        claim = claims[0]
        if _has_reference(claim, snaks):
            print(f"  #{st.n}: reference exists")
            continue
        client.set_reference(claim["id"], snaks)
        print(f"  #{st.n}: reference added to {claim['id']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply provenance references for the Ogham use case.")
    ap.add_argument("--dry-run", action="store_true", help="show plan; write nothing")
    args = ap.parse_args(argv)
    ensure_references(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
