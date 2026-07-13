#!/usr/bin/env python3
"""Orchestration: parse the job's .qs file and write claims via the API."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import ApiError, WikibaseClient
from .config import AppConfig
from .parser import ParseError, parse_qs_file

log = logging.getLogger("wb-qs-import")


def prepare_report_path(report_dir: Path) -> Path:
    """Timestamped report path inside report_dir (created if missing)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"import_report_{stamp}.json"
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir / name
    except OSError as exc:
        log.warning("Cannot use report dir %s (%s); writing report to current directory.", report_dir, exc)
        return Path(name)


def run(
    app: AppConfig,
    *,
    limit: int | None = None,
    federate_bare_qids: bool = False,
    federate_bare_pids: bool = False,
) -> int:
    """Run the import. Returns a process exit code (0/1/2)."""
    log.info("Input:      %s", app.qs_file)
    log.info("Report dir: %s", app.report_dir)

    try:
        statements = parse_qs_file(
            app.qs_file,
            federate_bare_qids=federate_bare_qids,
            federate_bare_pids=federate_bare_pids,
        )
    except (ParseError, FileNotFoundError) as exc:
        log.error("%s", exc)
        return 2

    if limit is not None:
        statements = statements[:limit]

    log.info("Parsed %d statement(s).", len(statements))
    for st in statements:
        prop_kind = "fed-prop" if st.is_federated_property else "local-prop"
        val_kind = "fed-val" if st.is_federated_value else "local-val"
        log.info("  L%d: %s | %s | %s  [%s, %s]", st.line_no, st.entity, st.prop,
                 json.dumps(st.value_api, ensure_ascii=False), prop_kind, val_kind)

    if not statements:
        log.info("Nothing to import.")
        return 0

    if app.dry_run:
        if app.using_example:
            log.warning("Using config.example.ini -> forced dry run. Copy it to "
                        "config.ini and add credentials to actually write.")
        log.info("Dry run enabled: no statements were written.")
        return 0

    if not app.username or not app.password or app.username == "YOUR_USERNAME":
        log.error("Missing credentials. Set them in config.ini or via "
                  "WIKIBASE_USERNAME / WIKIBASE_PASSWORD.")
        return 2

    client = WikibaseClient(
        app.api_url, app.username, app.password,
        user_agent=app.user_agent,
        maxlag=app.maxlag or None,
        mark_bot=app.mark_bot,
        throttle=app.throttle_seconds,
    )

    log.info("Logging in ...")
    client.login()
    client.csrf_token()

    report: list[dict[str, Any]] = []
    n_ok = n_skip = n_err = 0

    for st in statements:
        try:
            if app.skip_existing and client.claim_exists(st):
                log.info("SKIP existing L%d: %s", st.line_no, st.original.strip())
                report.append({"line": st.line_no, "status": "skipped_existing", "statement": st.original})
                n_skip += 1
                continue

            result = client.create_claim(st)
            claim_id = result.get("claim", {}).get("id")
            log.info("OK   L%d: %s", st.line_no, claim_id)
            report.append({
                "line": st.line_no, "status": "success",
                "claim_id": claim_id, "statement": st.original,
            })
            n_ok += 1
        except ApiError as exc:
            log.error("ERR  L%d: %s", st.line_no, exc)
            report.append({
                "line": st.line_no, "status": "error",
                "code": exc.code, "info": exc.info, "statement": st.original,
            })
            n_err += 1
        except Exception as exc:  # network, JSON, etc.
            log.error("ERR  L%d: %s", st.line_no, exc)
            report.append({
                "line": st.line_no, "status": "exception",
                "error": str(exc), "statement": st.original,
            })
            n_err += 1

    report_path = prepare_report_path(app.report_dir)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Done: %d ok, %d skipped, %d errors.", n_ok, n_skip, n_err)
    log.info("Report written to %s", report_path.resolve())
    return 1 if n_err else 0
