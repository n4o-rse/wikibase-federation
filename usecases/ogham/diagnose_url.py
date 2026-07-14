#!/usr/bin/env python3
"""
Diagnose why url-datatype values fail to save on Q5.

Writes a few probe claims to the hub item and removes any that succeed, so it
leaves no junk behind. The pattern of success/failure tells us the cause:

  probe A: local url prop (P4) + plain URL      (https://example.com)
  probe B: local url prop (P4) + entity-URI URL (FactGrid entity)
  probe C: federated url prop (wd:P2888) + plain URL

Interpretation:
  A ok, B fail          -> entity-URI-shaped URLs are rejected/intercepted
  A fail                -> url via API blocked on this instance in general
  A ok, C fail          -> the *federated* url property is the problem

Run:
    python usecases\\ogham\\diagnose_url.py
"""

from __future__ import annotations

import configparser
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

P_LOCAL_URL = "P4"  # has digital representation (adjust if your PID differs)
P_FED_URL = "http://www.wikidata.org/entity/P2888"  # exact match (federated)


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


def _probe(client: WikibaseClient, hub: str, prop: str, url: str, label: str) -> None:
    st = Statement(entity=hub, prop=prop, prop_raw=prop, value_raw=url,
                   value_api=url, line_no=0, original="", value_datatype="url")
    try:
        result = client.create_claim(st)
        claim_id = result.get("claim", {}).get("id")
        print(f"  [{label}] OK -> {claim_id}")
        if claim_id:
            client.remove_claim(claim_id)
            print(f"  [{label}] cleaned up.")
    except ApiError as exc:
        print(f"  [{label}] FAIL -> {exc}")


def main() -> int:
    hub = model.HUB_ITEM
    api, user, pw, ua = _cfg()
    client = WikibaseClient(api, user, pw, user_agent=ua)
    print(f"Logging in as {user} ...")
    client.login()
    print(f"Probing url writes on {hub}:")
    _probe(client, hub, P_LOCAL_URL, "https://example.com", "A local-prop plain-url")
    _probe(client, hub, P_LOCAL_URL,
           "https://database.factgrid.de/entity/Q1000294", "B local-prop entity-uri")
    _probe(client, hub, P_FED_URL, "https://example.com", "C fed-prop plain-url")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
