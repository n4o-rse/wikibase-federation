#!/usr/bin/env python3
"""
Import a small QuickStatements-like file into a Wikibase via the MediaWiki /
Wikibase Action API.

Primary use case: the Wikibase "Ontology Federation" / "Federated Values" alpha
feature, where a statement value is a *Wikidata* item referenced by its full
entity URI. That path currently does not work via QuickStatements, but does work
via ``wbcreateclaim`` with a value of the form::

    {"entity-type": "item", "id": "http://www.wikidata.org/entity/Q2016147"}

Run ``python import_qs_api.py --help`` for usage.
"""

from __future__ import annotations

import argparse
import configparser
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 ships with requests; import location is stable in practice.
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - extremely unlikely
    Retry = None  # type: ignore[assignment]

from qs_parser import ParseError, Statement, parse_qs_file

__version__ = "1.0.0"

# Directory this script lives in. Used so that config.ini / example.qs are found
# even when VS Code runs the file from a different working directory (e.g. via
# the editor "Run Python File" button / context menu).
SCRIPT_DIR = Path(__file__).resolve().parent

# Default I/O directories. Both can be overridden in config.ini
# ([import] data_dir / report_dir).
DEFAULT_DATA_DIR = Path("/root/data")
DEFAULT_REPORT_DIR = Path("/root/report")

DEFAULT_USER_AGENT = (
    f"wikibase-qs-api-importer/{__version__} "
    "(+https://github.com/USER/wikibase-qs-api-importer)"
)

log = logging.getLogger("wb-qs-import")


class ApiError(RuntimeError):
    """Raised when the MediaWiki API returns an ``error`` object."""

    def __init__(self, response: dict[str, Any]) -> None:
        err = response.get("error", {})
        self.code = err.get("code", "unknown")
        self.info = err.get("info", "")
        self.response = response
        super().__init__(f"API error [{self.code}]: {self.info}")


class WikibaseClient:
    """Thin, well-behaved client around the parts of the API we need."""

    def __init__(
        self,
        api_url: str,
        username: str,
        password: str,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        maxlag: int | None = None,
        mark_bot: bool = False,
        throttle: float = 0.0,
        timeout: int = 30,
    ) -> None:
        self.api_url = api_url
        self.username = username
        self.password = password
        self.maxlag = maxlag
        self.mark_bot = mark_bot
        self.throttle = throttle
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._configure_retries()

        self._csrf_token: str | None = None
        self._entity_cache: dict[str, dict[str, Any]] = {}

    # -- low level -----------------------------------------------------------

    def _configure_retries(self) -> None:
        """Retry transient network/5xx errors on *idempotent* GET requests only."""
        if Retry is None:
            return
        retry = Retry(
            total=4,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    @staticmethod
    def _check(result: dict[str, Any]) -> dict[str, Any]:
        if "error" in result:
            raise ApiError(result)
        return result

    def _get(self, params: dict[str, Any], *, check: bool = True) -> dict[str, Any]:
        params = {"format": "json", **params}
        r = self.session.get(self.api_url, params=params, timeout=self.timeout)
        r.raise_for_status()
        result = r.json()
        return self._check(result) if check else result

    def _post(self, data: dict[str, Any], *, check: bool = True) -> dict[str, Any]:
        data = {"format": "json", **data}
        if self.maxlag is not None:
            data.setdefault("maxlag", self.maxlag)
        r = self.session.post(self.api_url, data=data, timeout=self.timeout)
        r.raise_for_status()
        result = r.json()
        return self._check(result) if check else result

    # -- auth ----------------------------------------------------------------

    def login(self) -> None:
        login_token = self._get({
            "action": "query",
            "meta": "tokens",
            "type": "login",
        })["query"]["tokens"]["logintoken"]

        result = self._post({
            "action": "login",
            "lgname": self.username,
            "lgpassword": self.password,
            "lgtoken": login_token,
        })

        status = result.get("login", {}).get("result")
        if status != "Success":
            raise RuntimeError(
                "Login failed: "
                + json.dumps(result.get("login", result), ensure_ascii=False, indent=2)
                + "\nHint: use a Bot password (Special:BotPasswords). The username "
                "must then look like 'User@botname'."
            )
        log.info("Logged in as %s.", self.username)

    def csrf_token(self, *, force: bool = False) -> str:
        if self._csrf_token is None or force:
            self._csrf_token = self._get({
                "action": "query",
                "meta": "tokens",
            })["query"]["tokens"]["csrftoken"]
        return self._csrf_token

    # -- reads ---------------------------------------------------------------

    def get_entity(self, qid: str) -> dict[str, Any]:
        if qid not in self._entity_cache:
            result = self._get({"action": "wbgetentities", "ids": qid})
            entities = result.get("entities", {})
            entity = entities.get(qid, {})
            if entity.get("missing") is not None or "id" not in entity:
                raise ApiError({"error": {"code": "no-such-entity", "info": f"{qid} not found"}})
            self._entity_cache[qid] = entity
        return self._entity_cache[qid]

    def claim_exists(self, statement: Statement) -> bool:
        entity = self.get_entity(statement.entity)
        claims = entity.get("claims", {}).get(statement.prop, [])
        wanted_id = statement.value_api.get("id")
        for claim in claims:
            value = (
                claim.get("mainsnak", {})
                .get("datavalue", {})
                .get("value", {})
            )
            if isinstance(value, dict) and value.get("id") == wanted_id:
                return True
        return False

    # -- writes --------------------------------------------------------------

    def create_claim(self, statement: Statement) -> dict[str, Any]:
        """Create a single claim, handling maxlag and stale-token retries."""
        value = json.dumps(statement.value_api, ensure_ascii=False)
        max_attempts = 5

        for attempt in range(1, max_attempts + 1):
            data = {
                "action": "wbcreateclaim",
                "entity": statement.entity,
                "property": statement.prop,
                "snaktype": "value",
                "value": value,
                "token": self.csrf_token(),
                "assert": "user",
            }
            if self.mark_bot:
                data["bot"] = "1"

            # Don't auto-check here: we want to branch on specific error codes.
            result = self._post(data, check=False)

            if "error" not in result:
                if self.throttle:
                    time.sleep(self.throttle)
                # A new claim changes the entity; drop cached copy.
                self._entity_cache.pop(statement.entity, None)
                return result

            code = result["error"].get("code", "")
            if code in {"badtoken", "notoken"} and attempt < max_attempts:
                log.warning("CSRF token rejected (%s); refreshing and retrying.", code)
                self.csrf_token(force=True)
                continue
            if code == "maxlag" and attempt < max_attempts:
                wait = _retry_after_seconds(result, default=5 * attempt)
                log.warning("Server lag (maxlag); waiting %ss before retry.", wait)
                time.sleep(wait)
                continue

            # Non-retryable, or out of attempts: surface it to the caller.
            raise ApiError(result)

        raise ApiError({"error": {"code": "retries-exhausted", "info": "wbcreateclaim"}})


def _retry_after_seconds(result: dict[str, Any], *, default: int) -> float:
    lag = result.get("error", {}).get("lag")
    try:
        return max(float(lag), 1.0)
    except (TypeError, ValueError):
        return float(default)


# -- config ------------------------------------------------------------------


def _first_existing(names: list[str]) -> Path | None:
    """Return the first of ``names`` that exists in the cwd or next to the script."""
    for base in (Path.cwd(), SCRIPT_DIR):
        for name in names:
            candidate = base / name
            if candidate.is_file():
                return candidate
    return None


def resolve_config_path(explicit: Path | None) -> tuple[Path, bool]:
    """Locate the config file.

    Returns (path, is_example). ``is_example`` is True when we fell back to
    config.example.ini, in which case the caller should force a dry run because
    it contains only placeholder credentials.
    """
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"Config file not found: {explicit}")
        return explicit, False

    real = _first_existing(["config.ini"])
    if real is not None:
        return real, False

    example = _first_existing(["config.example.ini"])
    if example is not None:
        return example, True

    raise FileNotFoundError(
        "No config.ini found. Copy config.example.ini to config.ini and fill in "
        "your credentials."
    )


def resolve_input_path(
    explicit: Path | None,
    config: configparser.ConfigParser,
    data_dir: Path,
) -> Path:
    """Locate the statements file.

    Priority:
      1. explicit CLI argument,
      2. [import] input_file (absolute, or looked up in data_dir / cwd / script dir),
      3. the single ``*.qs`` file found in data_dir,
      4. a bundled input.qs / example.qs next to the script (first-run fallback).
    """
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"Input file not found: {explicit}")
        return explicit

    configured = config.get("import", "input_file", fallback="").strip()
    if configured:
        cand = Path(configured).expanduser()
        if cand.is_absolute():
            if cand.is_file():
                return cand
            raise FileNotFoundError(f"Configured input_file not found: {cand}")
        for base in (data_dir, Path.cwd(), SCRIPT_DIR):
            p = base / configured
            if p.is_file():
                return p
        raise FileNotFoundError(
            f"Configured input_file '{configured}' not found in {data_dir} (or cwd / script dir)."
        )

    if data_dir.is_dir():
        qs_files = sorted(data_dir.glob("*.qs"))
        if len(qs_files) == 1:
            return qs_files[0]
        if len(qs_files) > 1:
            names = ", ".join(p.name for p in qs_files)
            raise FileNotFoundError(
                f"Multiple .qs files in {data_dir}: {names}. Name one explicitly "
                "(python import_qs_api.py <file>) or set [import] input_file in config.ini."
            )

    fallback = _first_existing(["input.qs", "example.qs"])
    if fallback is None:
        raise FileNotFoundError(
            f"No input file found. Put a .qs file in {data_dir}, pass one on the "
            "command line, or set [import] input_file in config.ini."
        )
    return fallback


def prepare_report_path(report_dir: Path) -> Path:
    """Return a timestamped report path inside report_dir (created if missing).

    Falls back to the current directory if report_dir cannot be created.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"import_report_{stamp}.json"
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir / name
    except OSError as exc:
        log.warning("Cannot use report dir %s (%s); writing report to current directory.", report_dir, exc)
        return Path(name)


def read_config(path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    loaded = config.read(path, encoding="utf-8")
    if not loaded:
        raise FileNotFoundError(f"Config file not found: {path}")
    return config


def resolve_credentials(config: configparser.ConfigParser) -> tuple[str, str]:
    """Credentials from environment variables take precedence over config.ini."""
    username = os.environ.get("WIKIBASE_USERNAME") or config["wikibase"].get("username", "").strip()
    password = os.environ.get("WIKIBASE_PASSWORD") or config["wikibase"].get("password", "")
    if not username or not password or username == "YOUR_USERNAME":
        raise SystemExit(
            "Missing credentials. Set them in config.ini (or via the "
            "WIKIBASE_USERNAME / WIKIBASE_PASSWORD environment variables)."
        )
    return username, password


# -- CLI ---------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import QuickStatements-like item triples into a Wikibase via the API.",
    )
    parser.add_argument(
        "qs_file",
        type=Path,
        nargs="?",
        default=None,
        help="Input file with statements. If omitted, uses [import] input_file "
             "from config, else input.qs / example.qs next to the script.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.ini. If omitted, config.ini is auto-detected; "
             "config.example.ini is used as a read-only, dry-run fallback.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and print only; do not write.")
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Do not check for duplicate claims before writing.",
    )
    parser.add_argument(
        "--federate-bare-qids",
        action="store_true",
        help="Treat bare value Q-IDs as Wikidata IDs (Q3 P1 Q5 -> Wikidata Q5, not local Q5).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N statements.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose (DEBUG) logging.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Locate config first, tolerating a no-argument run (VS Code context menu).
    try:
        config_path, using_example = resolve_config_path(args.config)
        config = read_config(config_path)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 2

    api_url = config["wikibase"]["api_url"].strip()
    user_agent = config["wikibase"].get("user_agent", DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT

    config_dry_run = config.getboolean("import", "dry_run", fallback=False)
    skip_existing = config.getboolean("import", "skip_existing", fallback=True)
    maxlag_cfg = config.getint("import", "maxlag", fallback=0)
    mark_bot = config.getboolean("import", "mark_bot", fallback=False)
    throttle = config.getfloat("import", "throttle_seconds", fallback=0.0)

    data_dir = Path(config.get("import", "data_dir", fallback=str(DEFAULT_DATA_DIR))).expanduser()
    report_dir = Path(config.get("import", "report_dir", fallback=str(DEFAULT_REPORT_DIR))).expanduser()

    try:
        input_path = resolve_input_path(args.qs_file, config, data_dir)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 2

    log.info("Config: %s", config_path)
    log.info("Data dir: %s", data_dir)
    log.info("Report dir: %s", report_dir)
    log.info("Input:  %s", input_path)

    dry_run = args.dry_run or config_dry_run
    if using_example:
        # config.example.ini holds only placeholders: never write with it.
        dry_run = True
        log.warning("Using config.example.ini -> forced dry run. Copy it to "
                    "config.ini and add credentials to actually write.")
    if args.no_skip_existing:
        skip_existing = False

    # Parse first: fail fast on malformed input before any network call.
    try:
        statements = parse_qs_file(input_path, federate_bare_qids=args.federate_bare_qids)
    except (ParseError, FileNotFoundError) as exc:
        log.error("%s", exc)
        return 2

    if args.limit is not None:
        statements = statements[: args.limit]

    log.info("Parsed %d statement(s).", len(statements))
    for st in statements:
        prop_kind = "fed-prop" if st.is_federated_property else "local-prop"
        val_kind = "fed-val" if st.is_federated_value else "local-val"
        log.info("  L%d: %s | %s | %s  [%s, %s]", st.line_no, st.entity, st.prop,
                 json.dumps(st.value_api, ensure_ascii=False), prop_kind, val_kind)

    if not statements:
        log.info("Nothing to import.")
        return 0

    if dry_run:
        log.info("Dry run enabled: no statements were written.")
        return 0

    username, password = resolve_credentials(config)
    client = WikibaseClient(
        api_url, username, password,
        user_agent=user_agent,
        maxlag=maxlag_cfg or None,
        mark_bot=mark_bot,
        throttle=throttle,
    )

    log.info("Logging in ...")
    client.login()
    client.csrf_token()  # prime the token

    report: list[dict[str, Any]] = []
    n_ok = n_skip = n_err = 0

    for st in statements:
        try:
            if skip_existing and client.claim_exists(st):
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

    report_path = prepare_report_path(report_dir)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Done: %d ok, %d skipped, %d errors.", n_ok, n_skip, n_err)
    log.info("Report written to %s", report_path.resolve())
    return 1 if n_err else 0


if __name__ == "__main__":
    raise SystemExit(main())