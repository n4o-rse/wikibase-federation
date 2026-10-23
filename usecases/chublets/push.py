#!/usr/bin/env python3
"""Push the Chublets CSV model into a real Wikibase (S7g of wikibase-static).

Reads ``data/derived/entities/*.json`` (Wikibase JSON, written by ``from-csv`` in
the demo repository) and writes it with ``wbeditentity``.

Fixed settings (same as the software use case on federated-objects.de):
- every property is a LOCAL property; there are NO federated properties;
- item values may be FEDERATED Wikidata items (``http://www.wikidata.org/entity/Q..``):
  a Wikidata stub of the CSV (origin ``wikidata-stub``) is never created, it becomes
  the federated value taken from its P4 (``values = federated``, the default);
- ``url`` properties fall back to ``string`` (``url_as_string = true``, the default).

Phases (cumulative; whatever is already in the idmap is skipped):
- ``core``   Q1..Q3, P1..P10; the ids must come out the same as in the CSV, else abort;
- ``model``  all classes and properties of ``entities.csv`` (new ids, see idmap);
- ``items``  items of ``entities.csv``, filtered by ``origin`` and ``limit``.

The network is only touched for a real run (or ``--probe``). Nothing here reads the clock.
"""

from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WD = "http://www.wikidata.org/entity/"
CORE_ITEMS = ["Q1", "Q2", "Q3"]
CORE_PROPERTIES = [f"P{i}" for i in range(1, 11)]
CORE_IDS = CORE_ITEMS + CORE_PROPERTIES
PHASES = ("core", "model", "items")
ID_RE = re.compile(r"^([QP])(\d+)$")
SUMMARY = "chublets push (wikibase-federation, S7g)"


class PushAbort(RuntimeError):
    """A condition under which nothing further may be written."""


def _num(eid: str) -> int:
    return int(eid[1:])


def _sort_key(eid: str) -> tuple[str, int]:
    return (eid[0], _num(eid))


# --------------------------------------------------------------------------- source


@dataclass
class Source:
    """The demo repository as seen by the push."""

    entities: dict[str, dict[str, Any]]            # id -> Wikibase JSON
    meta: dict[str, dict[str, str]]                # id -> row of entities.csv (kind, origin, ...)

    def kind(self, eid: str) -> str:
        if eid in self.meta:
            return self.meta[eid]["kind"]
        return "property" if eid.startswith("P") else "item"

    def is_stub(self, eid: str) -> bool:
        return self.meta.get(eid, {}).get("origin") == "wikidata-stub"

    def wikidata_id(self, eid: str) -> str | None:
        """The Wikidata id of a stub: the first string value of its P4."""
        for claim in self.entities.get(eid, {}).get("claims", {}).get("P4", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, str) and re.fullmatch(r"Q\d+", value):
                return value
        return None


def load_source(source_dir: Path) -> Source:
    ent_dir = source_dir / "data" / "derived" / "entities"
    if not ent_dir.is_dir():
        raise PushAbort(f"no data/derived/entities in {source_dir}; run `python main.py from-csv` there first")
    entities = {}
    for f in sorted(ent_dir.glob("*.json")):
        if ID_RE.match(f.stem):
            entities[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    meta: dict[str, dict[str, str]] = {}
    csv_path = source_dir / "data" / "csv" / "entities.csv"
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                meta[row["id"]] = row
    return Source(entities, meta)


# --------------------------------------------------------------------------- settings


@dataclass
class Settings:
    values: str = "federated"          # federated | local
    url_as_string: bool = True
    throttle: float = 0.0
    core_ids: str = "same"             # same: Q1..Q3, P1..P10 must keep their ids | any: ids of the target

    def __post_init__(self) -> None:
        if self.values not in {"federated", "local"}:
            raise ValueError("values must be 'federated' or 'local'")
        if self.core_ids not in {"same", "any"}:
            raise ValueError("core_ids must be 'same' or 'any'")


# --------------------------------------------------------------------------- state files


class IdMap:
    """CSV id -> target id, one file per target (``idmap-<target>.csv``), written at once."""

    HEADER = ["source_id", "target_id", "label_en"]

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.map: dict[str, str] = {}
        if path is not None and path.is_file():
            with path.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    self.map[row["source_id"]] = row["target_id"]

    def add(self, source_id: str, target_id: str, label: str) -> None:
        self.map[source_id] = target_id
        if self.path is None:
            return
        new = not self.path.is_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            if new:
                w.writerow(self.HEADER)
            w.writerow([source_id, target_id, label])

    def max_numeric(self, letter: str) -> int:
        nums = [_num(t) for t in self.map.values() if t.startswith(letter)]
        return max(nums, default=0)


class ClaimState:
    """Source claim id -> target claim GUID (``state-<target>.json``)."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.data: dict[str, str] = {}
        if path is not None and path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- translation


@dataclass
class Deferred:
    reason: str


class Translator:
    """Source claims -> target claims: mapped ids, federated stubs, no source ids left."""

    def __init__(self, source: Source, idmap: IdMap, settings: Settings) -> None:
        self.source = source
        self.idmap = idmap
        self.settings = settings

    # -- entity references -----------------------------------------------------
    def entity_value(self, eid: str) -> dict[str, str] | Deferred:
        if eid in self.idmap.map:
            return {"entity-type": "property" if eid.startswith("P") else "item", "id": self.idmap.map[eid]}
        if self.settings.values == "federated" and self.source.is_stub(eid):
            wd = self.source.wikidata_id(eid)
            if wd is None:
                return Deferred(f"stub {eid} has no Wikidata id in P4")
            return {"entity-type": "item", "id": WD + wd}
        return Deferred(f"{eid} is not in the target yet")

    def prop(self, pid: str) -> str | Deferred:
        if pid in self.idmap.map:
            return self.idmap.map[pid]
        return Deferred(f"property {pid} is not in the target yet")

    # -- snaks -----------------------------------------------------------------
    def snak(self, snak: dict[str, Any]) -> dict[str, Any] | Deferred:
        target_prop = self.prop(snak["property"])
        if isinstance(target_prop, Deferred):
            return target_prop
        out: dict[str, Any] = {"snaktype": snak["snaktype"], "property": target_prop}
        if snak["snaktype"] != "value":
            return out
        dv = snak["datavalue"]
        if dv["type"] == "wikibase-entityid":
            value = self.entity_value(dv["value"]["id"])
            if isinstance(value, Deferred):
                return value
            out["datavalue"] = {"type": "wikibase-entityid", "value": value}
        elif dv["type"] == "quantity" and dv["value"].get("unit", "1") != "1":
            return Deferred("quantity with a unit is not supported yet")
        else:
            out["datavalue"] = {"type": dv["type"], "value": dv["value"]}
        return out

    def snak_group(self, group: dict[str, list[dict[str, Any]]], order: list[str] | None) -> tuple[dict, list[str]] | Deferred:
        result: dict[str, list[dict[str, Any]]] = {}
        for pid, snaks in group.items():
            translated = []
            for s in snaks:
                t = self.snak(s)
                if isinstance(t, Deferred):
                    return t
                translated.append(t)
            tp = self.prop(pid)
            if isinstance(tp, Deferred):
                return tp
            result[tp] = translated
        mapped_order = []
        for pid in (order or list(group)):
            tp = self.idmap.map.get(pid)
            if tp is not None and tp not in mapped_order:
                mapped_order.append(tp)
        return result, mapped_order

    def claim(self, claim: dict[str, Any]) -> dict[str, Any] | Deferred:
        main = self.snak(claim["mainsnak"])
        if isinstance(main, Deferred):
            return main
        out: dict[str, Any] = {"type": "statement", "rank": claim.get("rank", "normal"), "mainsnak": main}
        if claim.get("qualifiers"):
            q = self.snak_group(claim["qualifiers"], claim.get("qualifiers-order"))
            if isinstance(q, Deferred):
                return q
            out["qualifiers"], out["qualifiers-order"] = q
        refs = []
        for ref in claim.get("references", []):
            r = self.snak_group(ref["snaks"], ref.get("snaks-order"))
            if isinstance(r, Deferred):
                return r
            refs.append({"snaks": r[0], "snaks-order": r[1]})
        if refs:
            out["references"] = refs
        return out


def canonical_snak(snak: dict[str, Any]) -> str:
    dv = snak.get("datavalue")
    if dv is None:
        return f"{snak['property']}|{snak['snaktype']}"
    value = dv["value"]
    if dv["type"] == "wikibase-entityid":
        eid = value["id"]
        value = eid[len(WD):] if eid.startswith(WD) else eid
        if eid.startswith(WD):
            value = "wd:" + value
    return f"{snak['property']}|{snak['snaktype']}|{json.dumps(value, sort_keys=True, ensure_ascii=False)}"


def canonical_claim(claim: dict[str, Any]) -> str:
    quals = sorted(
        canonical_snak(s) for snaks in claim.get("qualifiers", {}).values() for s in snaks
    )
    return canonical_snak(claim["mainsnak"]) + "||" + ";".join(quals)


# --------------------------------------------------------------------------- plan and run


@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    adopted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed_entities: list[str] = field(default_factory=list)
    claims_written: int = 0
    claims_present: int = 0
    claims_deferred: list[dict[str, str]] = field(default_factory=list)
    claims_failed: list[dict[str, str]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)       # dry run: the list of calls
    write_calls: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "entities": {
                "created": len(self.created),
                "adopted": len(self.adopted),
                "skipped": len(self.skipped),
                "failed": len(self.failed_entities),
            },
            "claims": {
                "written": self.claims_written,
                "already_present": self.claims_present,
                "deferred": len(self.claims_deferred),
                "failed": len(self.claims_failed),
            },
            "write_calls": self.write_calls,
            "failed_entities": self.failed_entities,
            "claims_deferred": self.claims_deferred,
            "claims_failed": self.claims_failed,
            "calls": self.calls,
        }


def select(source: Source, phases: set[str], *, values: str, origins: set[str] | None = None, limit: int | None = None) -> list[str]:
    """The entity ids of the chosen phases, in the order in which they are created."""
    ids: list[str] = []
    if "core" in phases:
        ids += [i for i in CORE_ITEMS if i in source.entities]
        ids += [i for i in CORE_PROPERTIES if i in source.entities]

    def eligible(eid: str) -> bool:
        if eid in CORE_IDS or eid not in source.entities:
            return False
        return values == "local" or not source.is_stub(eid)

    if "model" in phases:
        classes = [i for i in source.meta if source.meta[i]["kind"] == "class" and eligible(i)]
        props = [i for i in source.meta if source.meta[i]["kind"] == "property" and eligible(i)]
        ids += sorted(classes, key=_sort_key) + sorted(props, key=_sort_key)
    if "items" in phases:
        items = [
            i for i in source.meta
            if source.meta[i]["kind"] == "item" and eligible(i)
            and (not origins or source.meta[i]["origin"] in origins)
        ]
        items = sorted(items, key=_sort_key)
        ids += items[:limit] if limit else items
    # items before properties inside the same list keeps both counters in order
    return ids


def entity_payload(src: dict[str, Any], settings: Settings) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key in ("labels", "descriptions"):
        if src.get(key):
            data[key] = {lang: {"language": lang, "value": v["value"]} for lang, v in src[key].items()}
    if src.get("aliases"):
        data["aliases"] = {
            lang: [{"language": lang, "value": a["value"]} for a in vals] for lang, vals in src["aliases"].items() if vals
        }
    if src["type"] == "property":
        datatype = src["datatype"]
        if datatype == "url" and settings.url_as_string:
            datatype = "string"
        data["datatype"] = datatype
    return data


def label_en(src: dict[str, Any]) -> str:
    labels = src.get("labels", {})
    return (labels.get("en") or next(iter(labels.values()), {"value": ""}))["value"]


def load_adopt(path: Path | None) -> dict[str, str]:
    """``adopt-<target>.csv``: source_id,target_id. Entities that already exist on the target."""
    out: dict[str, str] = {}
    if path is None or not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sid, tid = (row.get("source_id") or "").strip(), (row.get("target_id") or "").strip()
            if not sid or sid.startswith("#"):
                continue
            if not (ID_RE.match(sid) and ID_RE.match(tid)) or sid[0] != tid[0]:
                raise PushAbort(f"adopt file: {sid!r} -> {tid!r} is not a pair of the same kind (Q/P)")
            out[sid] = tid
    return out


def inventory(client: Any) -> list[dict[str, Any]]:
    """Read only: every item and property of the target with labels, for choosing what to adopt."""
    namespaces = client.entity_namespaces()
    ids: list[str] = []
    for model in ("wikibase-item", "wikibase-property"):
        if model not in namespaces:
            continue
        for title in client.list_titles(namespaces[model]):
            m = re.search(r"([QP]\d+)$", title)
            if m:
                ids.append(m.group(1))
    ids = sorted(set(ids), key=_sort_key)
    rows: list[dict[str, Any]] = []
    for eid, ent in client.get_entities(ids).items():
        if ent is None:
            continue
        labels = ent.get("labels", {})
        descs = ent.get("descriptions", {})
        rows.append({
            "id": eid,
            "type": "property" if eid.startswith("P") else "item",
            "datatype": ent.get("datatype", ""),
            "label_en": labels.get("en", {}).get("value", ""),
            "label_de": labels.get("de", {}).get("value", ""),
            "description_en": descs.get("en", {}).get("value", ""),
            "claims": sum(len(v) for v in ent.get("claims", {}).values()),
        })
    return sorted(rows, key=lambda r: _sort_key(r["id"]))


class Pusher:
    def __init__(
        self,
        source: Source,
        client: Any | None,
        idmap: IdMap,
        state: ClaimState,
        settings: Settings,
        *,
        dry_run: bool = True,
    ) -> None:
        if client is None and not dry_run:
            raise ValueError("a real run needs a client")
        self.source = source
        self.client = client
        self.idmap = idmap
        self.state = state
        self.settings = settings
        self.dry_run = dry_run
        self.report = Report()

    # -- adoption ----------------------------------------------------------------
    def adopt_existing(self, adopt: dict[str, str]) -> None:
        """Map source entities onto entities that already exist on the target.

        Checked in a real run: the target must hold the entity, its English label must equal the
        CSV label (ignoring case) and, for properties, the datatype must be the one we would create.
        """
        todo = {sid: tid for sid, tid in adopt.items() if sid in self.source.entities}
        remote = {} if self.dry_run or not todo else self.client.get_entities(sorted(set(todo.values())))
        for sid, tid in sorted(todo.items(), key=lambda kv: _sort_key(kv[0])):
            if sid in self.idmap.map:
                if self.idmap.map[sid] != tid:
                    raise PushAbort(f"adopt: {sid} is already mapped to {self.idmap.map[sid]}, not {tid}")
                continue
            src = self.source.entities[sid]
            label = label_en(src)
            if self.dry_run:
                self.idmap.map[sid] = tid
                self.report.calls.append(f"adopt {sid} -> {tid} {label!r} (not checked in a dry run)")
                self.report.adopted.append(sid)
                continue
            ent = remote.get(tid)
            if ent is None:
                raise PushAbort(f"adopt: {tid} does not exist on the target (for {sid} {label!r})")
            theirs = ent.get("labels", {}).get("en", {}).get("value", "")
            if theirs.strip().lower() != label.strip().lower():
                raise PushAbort(f"adopt: {tid} holds {theirs!r}, the CSV {sid} is {label!r}")
            if src["type"] == "property":
                want = entity_payload(src, self.settings)["datatype"]
                if ent.get("datatype") != want:
                    raise PushAbort(f"adopt: {tid} has datatype {ent.get('datatype')!r}, {sid} would be {want!r}")
            self.idmap.add(sid, tid, label)
            self.report.adopted.append(sid)

    # -- pass 1 ----------------------------------------------------------------
    def create_entities(self, ids: list[str]) -> None:
        for eid in ids:
            src = self.source.entities[eid]
            if eid in self.idmap.map:
                if eid not in self.report.adopted:
                    self.report.skipped.append(eid)
                continue
            payload = entity_payload(src, self.settings)
            new = src["type"]
            label = label_en(src)
            if eid in CORE_IDS and self.settings.core_ids == "same":
                self._create_core(eid, src, payload, new, label)
            else:
                self._create(eid, payload, new, label)

    def _create_core(self, eid: str, src: dict, payload: dict, new: str, label: str) -> None:
        if not self.dry_run:
            existing = self.client.get_entities([eid])[eid]
            if existing is not None:
                theirs = existing.get("labels", {}).get("en", {}).get("value")
                if theirs != label:
                    raise PushAbort(f"target {eid} already holds {theirs!r}, the CSV expects {label!r}; the core ids would differ")
                self.idmap.add(eid, eid, label)
                self.report.adopted.append(eid)
                return
        new_id = self._create(eid, payload, new, label)
        if new_id is not None and new_id != eid:
            raise PushAbort(f"core entity {eid} came out as {new_id} on the target; the target was not empty. Stop.")

    def _create(self, eid: str, payload: dict, new: str, label: str) -> str | None:
        letter = "Q" if new == "item" else "P"
        if self.dry_run:
            # the next id after the highest one known (adopted or predicted earlier); the real target decides
            predicted = f"{letter}{self.idmap.max_numeric(letter) + 1}"
            self.idmap.map[eid] = predicted           # in memory only, not written
            self.report.created.append(eid)
            self.report.calls.append(f"wbeditentity new={new} -> {predicted} (predicted) from {eid} {label!r}"
                                     + (f" datatype={payload['datatype']}" if new == "property" else ""))
            return predicted
        try:
            result = self.client.edit_entity(payload, new=new, summary=SUMMARY)
        except Exception as exc:                      # noqa: BLE001 - reported, the run goes on
            if eid in CORE_IDS and self.settings.core_ids == "same":
                raise PushAbort(f"creating core entity {eid} failed: {exc}") from exc
            self.report.failed_entities.append(f"{eid}: {exc}")
            return None
        self.report.write_calls += 1
        new_id = result["entity"]["id"]
        self.idmap.add(eid, new_id, label)
        self.report.created.append(eid)
        time.sleep(self.settings.throttle)
        return new_id

    # -- pass 2 ----------------------------------------------------------------
    def write_claims(self, ids: list[str]) -> None:
        """Claims of the chosen entities and of everything already on the target.

        The second group is what makes a later run finish the claims an earlier run had to
        defer (a value pointed at an entity that was not pushed yet).
        """
        tr = Translator(self.source, self.idmap, self.settings)
        scope = set(ids) | {i for i in self.idmap.map if i in self.source.entities}
        pending = sorted((i for i in scope if i in self.idmap.map), key=_sort_key)
        todo = {
            eid: [c for plist in self.source.entities[eid].get("claims", {}).values() for c in plist
                  if c["id"] not in self.state.data]
            for eid in pending
        }
        self.report.claims_present += sum(
            len(c) for plist in (self.source.entities[e].get("claims", {}).values() for e in pending) for c in plist
        ) - sum(len(v) for v in todo.values())
        remote: dict[str, dict | None] = {}
        if not self.dry_run:
            targets = [self.idmap.map[e] for e in pending if todo[e]]
            remote = self.client.get_entities(targets) if targets else {}
        for eid in pending:
            if not todo[eid]:
                continue
            target = self.idmap.map[eid]
            have = set()
            existing = remote.get(target) or {}
            for plist in existing.get("claims", {}).values():
                for c in plist:
                    have.add(canonical_claim(c))
            new_claims: list[tuple[str, dict[str, Any]]] = []
            for claim in sorted(todo[eid], key=lambda c: _sort_key(c["mainsnak"]["property"])):
                sid = claim["id"]
                t = tr.claim(claim)
                if isinstance(t, Deferred):
                    self.report.claims_deferred.append({"entity": eid, "claim": sid, "reason": t.reason})
                    continue
                if canonical_claim(t) in have:
                    self.report.claims_present += 1
                    self.state.data[sid] = "present-on-target"
                    continue
                new_claims.append((sid, t))
            if not new_claims:
                continue
            if self.dry_run:
                self.report.claims_written += len(new_claims)
                self.report.calls.append(f"wbeditentity id={target} claims={len(new_claims)} (source {eid})")
                continue
            self._send_claims(eid, target, new_claims)

    def _send_claims(self, eid: str, target: str, new_claims: list[tuple[str, dict[str, Any]]]) -> None:
        try:
            result = self.client.edit_entity({"claims": [c for _, c in new_claims]}, entity_id=target, summary=SUMMARY)
        except Exception as exc:                      # noqa: BLE001
            for sid, _ in new_claims:
                self.report.claims_failed.append({"entity": eid, "claim": sid, "reason": str(exc)})
            return
        self.report.write_calls += 1
        written = {}
        for plist in result.get("entity", {}).get("claims", {}).values():
            for c in plist:
                written.setdefault(canonical_claim(c), c["id"])
        for sid, claim in new_claims:
            guid = written.get(canonical_claim(claim))
            self.state.data[sid] = guid or "written-guid-unknown"
            self.report.claims_written += 1
        self.state.save()
        time.sleep(self.settings.throttle)

    # -- all -------------------------------------------------------------------
    def run(self, ids: list[str], adopt: dict[str, str] | None = None) -> Report:
        self.adopt_existing(adopt or {})
        self.create_entities(ids)
        self.write_claims(ids)
        if not self.dry_run:
            self.state.save()
        return self.report
