#!/usr/bin/env python3
"""Pipeline for the Chublets use case: push the CSV model into chublets-wikibase.de.

    python usecases\\chublets\\pipeline.py                          dry run, phases core + model
    python usecases\\chublets\\pipeline.py --probe                  read only: login, siteinfo, core ids
    python usecases\\chublets\\pipeline.py --write                  really write core + model
    python usecases\\chublets\\pipeline.py --write --phase items --origin open-archaeo --limit 20

Dry run is the default; a real run needs ``--write`` AND ``[chublets] allow_write = true`` in config.ini.
Settings (``[chublets]`` in config.ini): source_dir, target, values, url_as_string, allow_write.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))

import push  # noqa: E402
from wbqs.client import DEFAULT_USER_AGENT, WikibaseClient  # noqa: E402
from wbqs.config import ConfigError, read_config, resolve_config_path  # noqa: E402

log = logging.getLogger("chublets-push")


def _client(cp) -> WikibaseClient:
    return WikibaseClient(
        api_url=cp.get("wikibase", "api_url").strip(),
        username=os.environ.get("WIKIBASE_USERNAME") or cp.get("wikibase", "username", fallback="").strip(),
        password=os.environ.get("WIKIBASE_PASSWORD") or cp.get("wikibase", "password", fallback=""),
        user_agent=cp.get("wikibase", "user_agent", fallback=DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT,
        mark_bot=cp.getboolean("import", "mark_bot", fallback=False),
        throttle=cp.getfloat("import", "throttle_seconds", fallback=0.0),
    )


def probe(client: WikibaseClient, source: push.Source) -> int:
    """Read only: what the target is, and whether the core ids are free (or already the right ones)."""
    client.login()
    info = client.siteinfo()
    print(f"target: {info['sitename']!r}  {info['generator']}")
    print("extensions: " + ", ".join(info["extensions"]))
    ids = push.CORE_IDS
    found = client.get_entities(ids)
    clean = True
    for eid in ids:
        ent = found[eid]
        want = push.label_en(source.entities[eid]) if eid in source.entities else "?"
        if ent is None:
            print(f"  {eid:<4} free")
        else:
            have = ent.get("labels", {}).get("en", {}).get("value")
            same = have == want
            clean &= same
            print(f"  {eid:<4} holds {have!r}  ({'same as the CSV' if same else 'DIFFERENT from the CSV: ' + repr(want)})")
    print("core ids: " + ("free or already right" if clean else "NOT usable, the push would stop"))
    return 0 if clean else 1


def run(
    *,
    config_path: Path | None = None,
    dry_run: bool = True,
    limit: int | None = None,
    phases: set[str] | None = None,
    origins: set[str] | None = None,
    do_probe: bool = False,
) -> int:
    try:
        path, _ = resolve_config_path(config_path)
        cp = read_config(path)
    except ConfigError as exc:
        print(f"config error: {exc}")
        return 2
    base = path.resolve().parent
    section = cp["chublets"] if cp.has_section("chublets") else {}
    source_dir = Path(section.get("source_dir", "../chublets-wikibase-demo")).expanduser()
    if not source_dir.is_absolute():
        source_dir = (base / source_dir).resolve()
    target = section.get("target", "").strip() or cp.get("wikibase", "api_url").split("//")[-1].split("/")[0]
    settings = push.Settings(
        values=section.get("values", "federated").strip(),
        url_as_string=str(section.get("url_as_string", "true")).strip().lower() in {"1", "true", "yes"},
        throttle=cp.getfloat("import", "throttle_seconds", fallback=0.0),
    )
    allow_write = str(section.get("allow_write", "false")).strip().lower() in {"1", "true", "yes"}
    if not dry_run and not section.get("target", "").strip():
        print("[chublets] target is empty: name the target explicitly (e.g. chublets-wikibase.de) before writing; "
              "running as a dry run.")
        dry_run = True
    if not dry_run and not allow_write:
        print("allow_write = true is missing in [chublets] of config.ini; running as a dry run.")
        dry_run = True

    try:
        source = push.load_source(source_dir)
    except push.PushAbort as exc:
        print(f"abort: {exc}")
        return 2

    if do_probe:
        return probe(_client(cp), source)

    phases = phases or {"core", "model"}
    ids = push.select(source, phases, values=settings.values, origins=origins, limit=limit)
    print(f"source: {source_dir}  ({len(source.entities)} entities)")
    print(f"target: {target}  phases: {', '.join(p for p in push.PHASES if p in phases)}  "
          f"values={settings.values}  url_as_string={settings.url_as_string}  "
          f"{'DRY RUN' if dry_run else 'WRITE'}")
    print(f"selected: {len(ids)} entities")

    # A dry run reads idmap and state (so a second run shows 0 writes) but never writes them.
    idmap = push.IdMap(HERE / f"idmap-{target}.csv")
    state = push.ClaimState(HERE / f"state-{target}.json")
    client = None
    if not dry_run:
        client = _client(cp)
        client.login()
    pusher = push.Pusher(source, client, idmap, state, settings, dry_run=dry_run)
    try:
        report = pusher.run(ids)
    except push.PushAbort as exc:
        print(f"ABORT: {exc}")
        return 3

    out = report.as_dict()
    if dry_run:
        for line in report.calls:
            print("  " + line)
    summary = {k: v for k, v in out.items() if k in {"entities", "claims", "write_calls"}}
    print(json.dumps(summary, indent=1))
    for d in report.claims_deferred[:10]:
        print(f"  deferred {d['entity']} {d['claim']}: {d['reason']}")
    if len(report.claims_deferred) > 10:
        print(f"  ... {len(report.claims_deferred) - 10} more deferred (see the report)")
    for f in report.failed_entities[:10]:
        print(f"  FAILED {f}")
    report_dir = HERE / "report"
    report_dir.mkdir(exist_ok=True)
    name = "push-dry.json" if dry_run else "push-last.json"
    (report_dir / name).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"report: {report_dir / name}")
    return 1 if (report.failed_entities or report.claims_failed) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Push the Chublets CSV model into a real Wikibase.")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--write", action="store_true", help="really write (default: dry run)")
    ap.add_argument("--probe", action="store_true", help="read only: login, siteinfo, are the core ids free?")
    ap.add_argument("--phase", default="core,model", help="comma list of core, model, items (default core,model)")
    ap.add_argument("--origin", default="", help="items only: comma list of origins, e.g. open-archaeo,wikidata")
    ap.add_argument("--limit", type=int, default=None, help="items only: the first N items")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)-7s %(message)s")
    phases = {p.strip() for p in args.phase.split(",") if p.strip()}
    bad = phases - set(push.PHASES)
    if bad:
        ap.error(f"unknown phase: {', '.join(sorted(bad))}")
    origins = {o.strip() for o in args.origin.split(",") if o.strip()} or None
    return run(config_path=args.config, dry_run=not args.write, limit=args.limit,
               phases=phases, origins=origins, do_probe=args.probe)


if __name__ == "__main__":
    raise SystemExit(main())
