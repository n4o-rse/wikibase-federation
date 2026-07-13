#!/usr/bin/env python3
"""
Parsing of a small QuickStatements-like file into Wikibase API structures.

This module is intentionally free of any network / API code so it can be unit
tested in isolation.

Supported line format (tab- or whitespace-separated, 3 columns):

    <subject>            <property>              <value>

where
  * <subject> is always a LOCAL item (Q...), the item being edited,
  * <property> is either a LOCAL property (P...) or a FEDERATED Wikidata
    property (wd:P... / a Wikidata property URI),
  * <value> is either a LOCAL item (Q...) or a FEDERATED Wikidata item
    (wd:Q... / a Wikidata entity URI).

All four combinations are therefore possible, e.g.::

    Q3  P1         Q4          # local property  + local item value
    Q3  P1         wd:Q5       # local property  + federated item value
    Q3  wd:P5572   Q4          # federated prop  + local item value
    Q3  wd:P5572   wd:Q5       # federated prop  + federated item value

Scope: only ``wikibase-item`` values are supported (local or federated). Strings,
dates, quantities, coordinates, qualifiers, references, labels and descriptions
are deliberately out of scope (see README).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# A local item ID, e.g. Q3 (no leading zeros, positive).
LOCAL_QID = re.compile(r"^Q[1-9][0-9]*$", re.IGNORECASE)
# A local property ID, e.g. P1.
LOCAL_PID = re.compile(r"^P[1-9][0-9]*$", re.IGNORECASE)

# A full Wikidata item entity URI, capturing the Q-id.
WD_ITEM_URI = re.compile(
    r"^https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)$", re.IGNORECASE
)
# A full Wikidata property URI: both the entity form (.../entity/P..) and the
# truthy/direct form (.../prop/direct/P..) are accepted and normalised.
WD_PROP_URI = re.compile(
    r"^https?://www\.wikidata\.org/(?:entity|prop/direct)/(P[1-9][0-9]*)$",
    re.IGNORECASE,
)

# Canonical prefix used for federated Wikidata entities (items AND properties).
WIKIDATA_ENTITY_PREFIX = "http://www.wikidata.org/entity/"


class ParseError(ValueError):
    """Raised when a line, property or value cannot be parsed."""


@dataclass(frozen=True)
class Statement:
    """A single parsed statement, ready to be sent to the API."""

    entity: str          # local subject item, e.g. "Q3"
    prop: str            # API "property" param: "P1" OR a Wikidata property URI
    prop_raw: str        # original property token as written in the file
    value_raw: str       # original value token as written in the file
    value_api: dict      # value dict for wbcreateclaim (json.dumps'ed later)
    line_no: int         # 1-based source line number
    original: str        # original, untrimmed source line

    @property
    def is_federated_value(self) -> bool:
        """True if the value points at a foreign (Wikidata) item URI."""
        return str(self.value_api.get("id", "")).startswith("http")

    # Backwards-compatible alias.
    is_federated = is_federated_value

    @property
    def is_federated_property(self) -> bool:
        """True if the property is a foreign (Wikidata) property URI."""
        return self.prop.startswith("http")


def parse_property(prop: str, *, federate_bare_pids: bool = False) -> str:
    """Turn a property token into the string for wbcreateclaim's ``property``.

    Accepts:
      * ``P1``                                        -> local property "P1"
      * ``wd:P5572`` / ``wdt:P5572``                  -> federated Wikidata URI
      * ``http://www.wikidata.org/entity/P5572``      -> federated Wikidata URI
      * ``http://www.wikidata.org/prop/direct/P5572`` -> federated Wikidata URI

    Federated forms are normalised to the entity URI
    ``http://www.wikidata.org/entity/P...``.

    Args:
        federate_bare_pids: If True, a bare ``P...`` is treated as a *Wikidata*
            property instead of a local one.

    Raises:
        ParseError: If the token is not a supported property reference.
    """
    prop = prop.strip().strip('"').strip()

    uri_match = WD_PROP_URI.match(prop)
    if uri_match:
        pid = uri_match.group(1).upper()
        return f"{WIKIDATA_ENTITY_PREFIX}{pid}"

    low = prop.lower()
    if low.startswith("wd:") or low.startswith("wdt:"):
        pid = prop.split(":", 1)[1].strip().upper()
        if not LOCAL_PID.match(pid):
            raise ParseError(f"Invalid Wikidata property: {prop!r}")
        return f"{WIKIDATA_ENTITY_PREFIX}{pid}"

    if LOCAL_PID.match(prop):
        pid = prop.upper()
        if federate_bare_pids:
            return f"{WIKIDATA_ENTITY_PREFIX}{pid}"
        return pid

    raise ParseError(
        "Unsupported property (use 'P...', 'wd:P...' or a Wikidata property "
        f"URI): {prop!r}"
    )


def parse_value(value: str, *, federate_bare_qids: bool = False) -> dict:
    """Turn a single value token into a wbcreateclaim value dict.

    Args:
        value: The raw value token (e.g. ``Q4``, ``wd:Q4``, a Wikidata URI).
        federate_bare_qids: If True, a bare ``Q...`` is treated as a *Wikidata*
            item (foreign URI) instead of a local item.

    Returns:
        ``{"entity-type": "item", "id": "Q4"}`` (local) or
        ``{"entity-type": "item", "id": "http://www.wikidata.org/entity/Q4"}``
        (federated).

    Raises:
        ParseError: If the value is not a supported item reference.
    """
    value = value.strip().strip('"').strip()

    uri_match = WD_ITEM_URI.match(value)
    if uri_match:
        qid = uri_match.group(1).upper()
        return {"entity-type": "item", "id": f"{WIKIDATA_ENTITY_PREFIX}{qid}"}

    if value.lower().startswith("wd:"):
        qid = value.split(":", 1)[1].strip().upper()
        if not LOCAL_QID.match(qid):
            raise ParseError(f"Invalid Wikidata item: {value!r}")
        return {"entity-type": "item", "id": f"{WIKIDATA_ENTITY_PREFIX}{qid}"}

    if LOCAL_QID.match(value):
        qid = value.upper()
        if federate_bare_qids:
            return {"entity-type": "item", "id": f"{WIKIDATA_ENTITY_PREFIX}{qid}"}
        return {"entity-type": "item", "id": qid}

    raise ParseError(
        "Unsupported value (only local Q-IDs, 'wd:Q...' and Wikidata entity "
        f"URIs are supported): {value!r}"
    )


def parse_line(
    original: str,
    line_no: int,
    *,
    federate_bare_qids: bool = False,
    federate_bare_pids: bool = False,
) -> Statement | None:
    """Parse one source line into a Statement, or None if blank/comment."""
    line = original.strip()
    if not line or line.startswith("#"):
        return None

    # Prefer tab separation (QuickStatements style); fall back to whitespace.
    parts = line.split("\t")
    if len(parts) < 3:
        parts = re.split(r"\s+", line, maxsplit=2)

    if len(parts) != 3:
        raise ParseError(f"Line {line_no}: expected 3 columns, got {len(parts)}: {original!r}")

    entity, prop_raw, value_raw = (p.strip() for p in parts)

    if not LOCAL_QID.match(entity):
        raise ParseError(
            f"Line {line_no}: subject must be a LOCAL item (Q...), got: {entity!r}"
        )

    try:
        prop = parse_property(prop_raw, federate_bare_pids=federate_bare_pids)
        value_api = parse_value(value_raw, federate_bare_qids=federate_bare_qids)
    except ParseError as exc:
        raise ParseError(f"Line {line_no}: {exc}") from exc

    return Statement(
        entity=entity.upper(),
        prop=prop,
        prop_raw=prop_raw,
        value_raw=value_raw,
        value_api=value_api,
        line_no=line_no,
        original=original,
    )


def parse_qs_file(
    path: Path,
    *,
    federate_bare_qids: bool = False,
    federate_bare_pids: bool = False,
) -> list[Statement]:
    """Parse a whole file into a list of Statements.

    Blank lines and lines starting with ``#`` are ignored. Raises ParseError on
    the first malformed line so problems are surfaced before any write happens.
    """
    statements: list[Statement] = []
    text = Path(path).read_text(encoding="utf-8")
    for line_no, original in enumerate(text.splitlines(), start=1):
        statement = parse_line(
            original,
            line_no,
            federate_bare_qids=federate_bare_qids,
            federate_bare_pids=federate_bare_pids,
        )
        if statement is not None:
            statements.append(statement)
    return statements