#!/usr/bin/env python3
"""
Parsing of a small QuickStatements-like file into Wikibase API value structures.

This module is intentionally free of any network / API code so it can be unit
tested in isolation.

Supported line format (tab- or whitespace-separated, 3 columns):

    Q3<TAB>P1<TAB>Q4                                     local item value
    Q3<TAB>P1<TAB>http://www.wikidata.org/entity/Q2016147  federated Wikidata item
    Q3<TAB>P1<TAB>wd:Q2016147                             federated Wikidata item
    Q3 P1 Q4                                              whitespace separated

Scope:
- Only ``wikibase-item`` values are supported, including federated Wikidata
  item URIs. Strings, dates, quantities, coordinates, qualifiers, references,
  labels and descriptions are deliberately out of scope (see README).
- The value dict returned mirrors exactly what ``wbcreateclaim`` expects as its
  ``value`` parameter (after ``json.dumps``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# A local entity ID, e.g. Q3 (no leading zeros, positive).
LOCAL_QID = re.compile(r"^Q[1-9][0-9]*$")
# A property ID, e.g. P1.
PID = re.compile(r"^P[1-9][0-9]*$")
# A full Wikidata entity URI (http or https), capturing the Q-id.
WD_URI = re.compile(
    r"^https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)$",
    re.IGNORECASE,
)

# Canonical prefix used for federated Wikidata item values.
WIKIDATA_ENTITY_PREFIX = "http://www.wikidata.org/entity/"


class ParseError(ValueError):
    """Raised when a line or value cannot be parsed."""


@dataclass(frozen=True)
class Statement:
    """A single parsed statement, ready to be sent to the API."""

    entity: str          # local subject item, e.g. "Q3"
    prop: str            # property, e.g. "P1"
    value_raw: str       # original value token as written in the file
    value_api: dict      # value dict for wbcreateclaim (json.dumps'ed later)
    line_no: int         # 1-based source line number
    original: str        # original, untrimmed source line

    @property
    def is_federated(self) -> bool:
        """True if the value points at a foreign (Wikidata) entity URI."""
        return str(self.value_api.get("id", "")).startswith("http")


def parse_value(value: str, *, federate_bare_qids: bool = False) -> dict:
    """Turn a single value token into a wbcreateclaim value dict.

    Args:
        value: The raw value token (e.g. ``Q4``, ``wd:Q4``, a Wikidata URI).
        federate_bare_qids: If True, a bare ``Q...`` is treated as a *Wikidata*
            item (foreign URI) instead of a local item. Useful when the whole
            file references Wikidata rather than local items.

    Returns:
        A dict such as ``{"entity-type": "item", "id": "Q4"}`` (local) or
        ``{"entity-type": "item", "id": "http://www.wikidata.org/entity/Q4"}``
        (federated).

    Raises:
        ParseError: If the value is not a supported item reference.
    """
    value = value.strip().strip('"').strip()

    # 1) Full Wikidata entity URI -> federated value.
    uri_match = WD_URI.match(value)
    if uri_match:
        qid = uri_match.group(1).upper()
        return {"entity-type": "item", "id": f"{WIKIDATA_ENTITY_PREFIX}{qid}"}

    # 2) wd:Q123 prefix -> federated value.
    if value.lower().startswith("wd:"):
        qid = value.split(":", 1)[1].strip().upper()
        if not LOCAL_QID.match(qid):
            raise ParseError(f"Invalid Wikidata ID: {value!r}")
        return {"entity-type": "item", "id": f"{WIKIDATA_ENTITY_PREFIX}{qid}"}

    # 3) Bare Q123 -> local (or federated, if requested).
    if LOCAL_QID.match(value.upper()):
        qid = value.upper()
        if federate_bare_qids:
            return {"entity-type": "item", "id": f"{WIKIDATA_ENTITY_PREFIX}{qid}"}
        return {"entity-type": "item", "id": qid}

    raise ParseError(
        "Unsupported value (only local Q-IDs, 'wd:Q...' and Wikidata entity "
        f"URIs are supported): {value!r}"
    )


def parse_line(original: str, line_no: int, *, federate_bare_qids: bool = False) -> Statement | None:
    """Parse one source line into a Statement, or None if it is blank/comment."""
    line = original.strip()
    if not line or line.startswith("#"):
        return None

    # Prefer tab separation (QuickStatements style); fall back to whitespace.
    parts = line.split("\t")
    if len(parts) < 3:
        parts = re.split(r"\s+", line, maxsplit=2)

    if len(parts) != 3:
        raise ParseError(f"Line {line_no}: expected 3 columns, got {len(parts)}: {original!r}")

    entity, prop, value_raw = (p.strip() for p in parts)

    if not LOCAL_QID.match(entity):
        raise ParseError(f"Line {line_no}: invalid subject entity ID: {entity!r}")
    if not PID.match(prop):
        raise ParseError(f"Line {line_no}: invalid property ID: {prop!r}")

    value_api = parse_value(value_raw, federate_bare_qids=federate_bare_qids)
    return Statement(entity, prop, value_raw, value_api, line_no, original)


def parse_qs_file(path: Path, *, federate_bare_qids: bool = False) -> list[Statement]:
    """Parse a whole file into a list of Statements.

    Blank lines and lines starting with ``#`` are ignored. Raises ParseError on
    the first malformed line so problems are surfaced before any write happens.
    """
    statements: list[Statement] = []
    text = Path(path).read_text(encoding="utf-8")
    for line_no, original in enumerate(text.splitlines(), start=1):
        statement = parse_line(original, line_no, federate_bare_qids=federate_bare_qids)
        if statement is not None:
            statements.append(statement)
    return statements
