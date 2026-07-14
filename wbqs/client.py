#!/usr/bin/env python3
"""Thin, well-behaved client around the Wikibase Action API parts we need."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 ships with requests; import location is stable in practice.
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - extremely unlikely
    Retry = None  # type: ignore[assignment]

from .parser import Statement

__version__ = "1.1.0"

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
        self.messages = err.get("messages")
        self.response = response
        self.detail = _extract_message_names(self.messages)
        msg = f"API error [{self.code}]: {self.info}"
        if self.detail:
            msg += f" -> {self.detail}"
        super().__init__(msg)


def _extract_message_names(messages: Any) -> str:
    """Pull the message names/text out of a MediaWiki error 'messages' block."""
    if not isinstance(messages, list):
        return ""
    out: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        name = m.get("name")
        html = m.get("html")
        text = html.get("*") if isinstance(html, dict) else None
        piece = name or ""
        if text and text != name:
            piece = f"{piece}: {text}" if piece else text
        if piece:
            out.append(piece)
    return " | ".join(out)


class WikibaseClient:
    """Client for login + wbcreateclaim, handling tokens, maxlag and retries."""

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
        wanted = statement.value_api
        dt = statement.value_datatype
        for claim in claims:
            value = (
                claim.get("mainsnak", {})
                .get("datavalue", {})
                .get("value")
            )
            if dt == "wikibase-item":
                if isinstance(value, dict) and isinstance(wanted, dict) \
                        and value.get("id") == wanted.get("id"):
                    return True
            elif dt == "monolingual":
                if isinstance(value, dict) and isinstance(wanted, dict) \
                        and value.get("text") == wanted.get("text") \
                        and value.get("language") == wanted.get("language"):
                    return True
            elif dt == "globe-coordinate":
                if isinstance(value, dict) and isinstance(wanted, dict) \
                        and _coord_close(value, wanted):
                    return True
            else:
                if value == wanted:
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

            result = self._post(data, check=False)

            if "error" not in result:
                if self.throttle:
                    time.sleep(self.throttle)
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

            raise ApiError(result)

        raise ApiError({"error": {"code": "retries-exhausted", "info": "wbcreateclaim"}})

    # -- entity creation -----------------------------------------------------

    def create_entity(
        self,
        *,
        new: str,
        labels: dict[str, str] | None = None,
        descriptions: dict[str, str] | None = None,
        aliases: dict[str, list[str]] | None = None,
        datatype: str | None = None,
    ) -> dict[str, Any]:
        """Create a new item or property via wbeditentity.

        new:        "item" or "property".
        datatype:   required when new == "property" (e.g. "url", "external-id").
        Returns the API result; the new id is at result["entity"]["id"].
        """
        data: dict[str, Any] = {}
        if labels:
            data["labels"] = {lang: {"language": lang, "value": v} for lang, v in labels.items()}
        if descriptions:
            data["descriptions"] = {lang: {"language": lang, "value": v} for lang, v in descriptions.items()}
        if aliases:
            data["aliases"] = {
                lang: [{"language": lang, "value": a} for a in vals]
                for lang, vals in aliases.items()
            }
        if new == "property":
            if not datatype:
                raise ValueError("datatype is required when creating a property")
            data["datatype"] = datatype

        params = {
            "action": "wbeditentity",
            "new": new,
            "data": json.dumps(data, ensure_ascii=False),
            "token": self.csrf_token(),
            "assert": "user",
        }
        if self.mark_bot:
            params["bot"] = "1"

        result = self._post(params, check=False)
        if "error" in result:
            code = result["error"].get("code", "")
            if code in {"badtoken", "notoken"}:
                self.csrf_token(force=True)
                params["token"] = self.csrf_token()
                result = self._post(params, check=False)
        return self._check(result)

    def remove_claim(self, claim_id: str) -> dict[str, Any]:
        """Remove a single claim by its GUID (wbremoveclaims)."""
        data = {
            "action": "wbremoveclaims",
            "claim": claim_id,
            "token": self.csrf_token(),
            "assert": "user",
        }
        if self.mark_bot:
            data["bot"] = "1"
        result = self._post(data, check=False)
        if "error" in result:
            code = result["error"].get("code", "")
            if code in {"badtoken", "notoken"}:
                self.csrf_token(force=True)
                data["token"] = self.csrf_token()
                result = self._post(data, check=False)
        return self._check(result)

    def set_reference(self, claim_id: str, snaks: dict[str, Any]) -> dict[str, Any]:
        """Add a reference (snaks map property->[snak]) to a claim (wbsetreference)."""
        data = {
            "action": "wbsetreference",
            "statement": claim_id,
            "snaks": json.dumps(snaks, ensure_ascii=False),
            "token": self.csrf_token(),
            "assert": "user",
        }
        if self.mark_bot:
            data["bot"] = "1"
        result = self._post(data, check=False)
        if "error" in result:
            code = result["error"].get("code", "")
            if code in {"badtoken", "notoken"}:
                self.csrf_token(force=True)
                data["token"] = self.csrf_token()
                result = self._post(data, check=False)
        return self._check(result)


def _coord_close(a: dict[str, Any], b: dict[str, Any], tol: float = 1e-5) -> bool:
    try:
        return (abs(float(a.get("latitude")) - float(b.get("latitude"))) <= tol
                and abs(float(a.get("longitude")) - float(b.get("longitude"))) <= tol)
    except (TypeError, ValueError):
        return False


def _retry_after_seconds(result: dict[str, Any], *, default: int) -> float:
    lag = result.get("error", {}).get("lag")
    try:
        return max(float(lag), 1.0)
    except (TypeError, ValueError):
        return float(default)