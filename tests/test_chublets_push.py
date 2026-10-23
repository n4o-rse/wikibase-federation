"""Tests of usecases/chublets/push.py against a fake Wikibase API (no network)."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "usecases" / "chublets"))

import push  # noqa: E402

WD = push.WD


# -- a fake Wikibase ---------------------------------------------------------


class FakeWikibase:
    """Just enough of wbeditentity / wbgetentities: counters, labels, claims with GUIDs."""

    def __init__(self, preset: dict[str, str] | None = None) -> None:
        self.entities: dict[str, dict] = {}
        self.counter = {"Q": 0, "P": 0}
        self.throttle = 0.0
        self.calls: list[tuple] = []
        self.fail_labels: set[str] = set()
        self.property_datatypes: dict[str, str] = {}
        for eid, label in (preset or {}).items():
            self.entities[eid] = {"id": eid, "labels": {"en": {"language": "en", "value": label}}, "claims": {}}
            self.counter[eid[0]] = max(self.counter[eid[0]], int(eid[1:]))

    def login(self) -> None:
        pass

    def get_entities(self, ids):
        self.calls.append(("get", tuple(ids)))
        return {i: self.entities.get(i) for i in ids}

    def edit_entity(self, data, *, entity_id=None, new=None, summary=None):
        self.calls.append(("edit", entity_id, new, data))
        if new:
            label = data.get("labels", {}).get("en", {}).get("value", "")
            if label in self.fail_labels:
                raise RuntimeError("modification-failed: label conflict")
            letter = "Q" if new == "item" else "P"
            self.counter[letter] += 1
            eid = f"{letter}{self.counter[letter]}"
            ent = {"id": eid, "labels": data.get("labels", {}), "claims": {}}
            if new == "property":
                ent["datatype"] = data["datatype"]
                self.property_datatypes[eid] = data["datatype"]
            self.entities[eid] = ent
            return {"success": 1, "entity": ent}
        ent = self.entities[entity_id]
        for claim in data.get("claims", []):
            claim = json.loads(json.dumps(claim))
            claim["id"] = f"{entity_id}${len(ent['claims']) + 1:04d}-guid"
            ent["claims"].setdefault(claim["mainsnak"]["property"], []).append(claim)
        return {"success": 1, "entity": ent}

    @property
    def writes(self) -> int:
        return sum(1 for c in self.calls if c[0] == "edit")


# -- a tiny source repository --------------------------------------------------


def _label(text: str) -> dict:
    return {"en": {"language": "en", "value": text}}


def _snak(prop: str, datatype: str, value, kind: str = "string") -> dict:
    if kind == "entity":
        dv = {"type": "wikibase-entityid", "value": {"entity-type": "item", "id": value, "numeric-id": int(value[1:])}}
    else:
        dv = {"type": "string", "value": value}
    return {"snaktype": "value", "property": prop, "datatype": datatype, "datavalue": dv}


def _claim(cid: str, prop: str, datatype: str, value, kind: str = "string", *, qualifiers=None, references=None) -> dict:
    c = {"id": cid, "type": "statement", "rank": "normal", "mainsnak": _snak(prop, datatype, value, kind)}
    if qualifiers:
        c["qualifiers"] = qualifiers
        c["qualifiers-order"] = list(qualifiers)
    if references:
        c["references"] = references
    return c


def _entity(eid: str, label: str, claims: list[dict] | None = None, datatype: str | None = None) -> dict:
    ent = {
        "type": "property" if eid.startswith("P") else "item",
        "id": eid,
        "labels": _label(label),
        "descriptions": {},
        "aliases": {},
        "claims": {},
    }
    if datatype:
        ent["datatype"] = datatype
    for c in claims or []:
        ent["claims"].setdefault(c["mainsnak"]["property"], []).append(c)
    return ent


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    ents: list[dict] = []
    # core
    ents += [
        _entity("Q1", "Class", [_claim("Q1$1", "P2", "wikibase-item", "Q2", "entity")]),
        _entity("Q2", "Property"),
        _entity("Q3", "Instance"),
    ]
    core_types = {"P1": "wikibase-item", "P2": "wikibase-item", "P3": "wikibase-property", "P4": "external-id",
                  "P5": "string", "P6": "url", "P7": "time", "P8": "wikibase-item", "P9": "wikibase-item",
                  "P10": "wikibase-item"}
    for pid, dt in core_types.items():
        ents.append(_entity(pid, f"core {pid}", [_claim(f"{pid}$1", "P2", "wikibase-item", "Q2", "entity")], dt))
    # model: a class, a stub class, a local property and a url property
    ents += [
        _entity("Q100", "software", [
            _claim("Q100$a", "P1", "wikibase-item", "Q3", "entity"),
            _claim("Q100$b", "P4", "external-id", "Q7397",
                   references=[{"snaks": {"P6": [_snak("P6", "url", "https://www.wikidata.org/wiki/Q7397")]},
                                "snaks-order": ["P6"]}]),
        ]),
        _entity("Q101", "chublet", [_claim("Q101$a", "P1", "wikibase-item", "Q100", "entity")]),
        _entity("Q150", "programming language", [_claim("Q150$a", "P4", "external-id", "Q9143")]),
        _entity("P100", "developer", [_claim("P100$a", "P9", "wikibase-item", "Q100", "entity")], "wikibase-item"),
        _entity("P101", "repository", [], "url"),
    ]
    # items
    ents += [
        _entity("Q200", "Tool A", [
            _claim("Q200$a", "P2", "wikibase-item", "Q101", "entity"),
            _claim("Q200$b", "P101", "url", "https://example.org/a", qualifiers={
                "P6": [_snak("P6", "url", "https://example.org/q")]}),
            _claim("Q200$c", "P100", "wikibase-item", "Q150", "entity"),
        ]),
        _entity("Q201", "Tool B", [_claim("Q201$a", "P2", "wikibase-item", "Q101", "entity")]),
        _entity("Q202", "Tool C", [_claim("Q202$a", "P100", "wikibase-item", "Q201", "entity")]),
    ]
    ed = tmp_path / "data" / "derived" / "entities"
    ed.mkdir(parents=True)
    for e in ents:
        (ed / f"{e['id']}.json").write_text(json.dumps(e), encoding="utf-8")
    rows = [
        ("Q100", "class", "", "starter-pack"), ("Q101", "class", "", "starter-pack"),
        ("Q150", "class", "", "wikidata-stub"),
        ("P100", "property", "wikibase-item", "starter-pack"), ("P101", "property", "url", "starter-pack"),
        ("Q200", "item", "", "open-archaeo"), ("Q201", "item", "", "open-archaeo"), ("Q202", "item", "", "wikidata"),
    ]
    cd = tmp_path / "data" / "csv"
    cd.mkdir(parents=True)
    with (cd / "entities.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["id", "kind", "datatype", "origin", "label_en"])
        for r in rows:
            w.writerow([*r, ""])
    return tmp_path


def make(source_dir: Path, tmp_path: Path, client, *, dry_run=False, values="federated", url_as_string=True):
    src = push.load_source(source_dir)
    idmap = push.IdMap(tmp_path / "idmap-test.csv")
    state = push.ClaimState(tmp_path / "state-test.json")
    settings = push.Settings(values=values, url_as_string=url_as_string)
    return src, push.Pusher(src, client, idmap, state, settings, dry_run=dry_run)


def run_phases(source_dir, tmp_path, client, phases, **kw):
    dry = kw.pop("dry_run", False)
    values = kw.pop("values", "federated")
    origins = kw.pop("origins", None)
    limit = kw.pop("limit", None)
    src, pusher = make(source_dir, tmp_path, client, dry_run=dry, values=values, **kw)
    ids = push.select(src, set(phases), values=values, origins=origins, limit=limit)
    report = pusher.run(ids)
    return src, pusher, report


# -- tests -------------------------------------------------------------------


def test_dry_run_lists_calls_and_writes_nothing(source_dir, tmp_path):
    fake = FakeWikibase()
    _, pusher, rep = run_phases(source_dir, tmp_path, None, ["core", "model"], dry_run=True)
    assert fake.calls == []
    assert len(rep.created) == 13 + 2 + 2          # core + 2 classes + 2 properties (stub not selected)
    assert rep.write_calls == 0
    assert any("new=item -> Q1 (predicted)" in c for c in rep.calls)
    assert not (tmp_path / "idmap-test.csv").exists()
    assert not (tmp_path / "state-test.json").exists()


def test_core_gets_the_csv_ids_and_second_run_writes_nothing(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core"])
    assert all(fake.entities[i]["labels"]["en"]["value"] for i in push.CORE_IDS)
    assert {i for i in push.CORE_IDS} <= set(fake.entities)
    first = fake.writes
    assert first == 13 + 11                       # 13 creates, 11 claim calls (Q2 and Q3 have no claims)
    _, _, rep = run_phases(source_dir, tmp_path, fake, ["core"])
    assert fake.writes == first                    # nothing written again
    assert rep.write_calls == 0 and rep.claims_written == 0


def test_core_aborts_when_target_holds_something_else(source_dir, tmp_path):
    fake = FakeWikibase({"Q1": "Something else"})
    with pytest.raises(push.PushAbort, match="Q1"):
        run_phases(source_dir, tmp_path, fake, ["core"])
    assert fake.writes == 0


def test_core_aborts_when_ids_would_differ(source_dir, tmp_path):
    fake = FakeWikibase()
    fake.counter["Q"] = 5                          # the target's next item is Q6, not Q1
    with pytest.raises(push.PushAbort, match="not empty"):
        run_phases(source_dir, tmp_path, fake, ["core"])


def test_core_adopts_an_already_correct_target(source_dir, tmp_path):
    fake = FakeWikibase({"Q1": "Class"})
    _, _, rep = run_phases(source_dir, tmp_path, fake, ["core"])
    assert "Q1" in rep.adopted and fake.entities["Q2"]["labels"]["en"]["value"] == "Property"


def test_model_gets_new_ids_and_values_are_remapped(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core"])
    src, pusher, rep = run_phases(source_dir, tmp_path, fake, ["model"])
    idm = pusher.idmap.map
    assert idm["Q100"] == "Q4" and idm["Q101"] == "Q5"
    assert idm["P100"] == "P11" and idm["P101"] == "P12"
    # the class Q101 'chublet' is a subclass (P1) of the software class: Q100 -> Q4
    claim = fake.entities["Q5"]["claims"]["P1"][0]
    assert claim["mainsnak"]["datavalue"]["value"]["id"] == "Q4"
    # the idmap file is written
    rows = list(csv.DictReader((tmp_path / "idmap-test.csv").open(encoding="utf-8")))
    assert {r["source_id"]: r["target_id"] for r in rows}["P100"] == "P11"


def test_url_property_falls_back_to_string_and_can_be_switched_off(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    assert fake.property_datatypes["P12"] == "string"        # P101 (url)
    assert fake.property_datatypes["P6"] == "string"         # core P6 (url) too
    fake2 = FakeWikibase()
    t2 = tmp_path / "second"
    t2.mkdir()
    run_phases(source_dir, t2, fake2, ["core", "model"], url_as_string=False)
    assert fake2.property_datatypes["P12"] == "url"


def test_stub_becomes_federated_value_and_no_source_id_leaks(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    run_phases(source_dir, tmp_path, fake, ["items"], origins={"open-archaeo"})
    q200 = next(e for e in fake.entities.values() if e["labels"]["en"]["value"] == "Tool A")
    value = q200["claims"]["P11"][0]["mainsnak"]["datavalue"]["value"]   # P100 developer -> P11, value stub Q150
    assert value["id"] == WD + "Q9143"
    # no stub item was created and no source-only id appears in any value
    assert "programming language" not in {e["labels"]["en"]["value"] for e in fake.entities.values()}
    dumped = json.dumps([c for e in fake.entities.values() for c in e["claims"].values()])
    for foreign in ("Q150", "Q200", "Q201", "P100", "P101"):
        assert f'"{foreign}"' not in dumped


def test_no_federated_properties(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    run_phases(source_dir, tmp_path, fake, ["items"])
    for e in fake.entities.values():
        for pid, claims in e["claims"].items():
            assert re.fullmatch(r"P\d+", pid)
            for c in claims:
                assert re.fullmatch(r"P\d+", c["mainsnak"]["property"])


def test_values_local_creates_the_stub_as_an_item(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"], values="local")
    labels = {e["labels"]["en"]["value"] for e in fake.entities.values()}
    assert "programming language" in labels


def test_qualifiers_and_references_arrive_mapped(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    run_phases(source_dir, tmp_path, fake, ["items"], origins={"open-archaeo"})
    q4 = fake.entities["Q4"]                                   # class software, P4 with a P6 reference
    ref = q4["claims"]["P4"][0]["references"][0]
    assert list(ref["snaks"]) == ["P6"]
    tool = next(e for e in fake.entities.values() if e["labels"]["en"]["value"] == "Tool A")
    c = tool["claims"]["P12"][0]                               # repository, with qualifier P6
    assert c["qualifiers"]["P6"][0]["datavalue"]["value"] == "https://example.org/q"
    assert "hash" not in json.dumps(c) and "datatype" not in json.dumps(c)


def test_claim_to_unpushed_entity_is_deferred_then_finished_by_a_later_run(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    # Tool C (Q202, origin wikidata) points at Tool B (Q201, open-archaeo), pushed in the second step
    _, _, rep = run_phases(source_dir, tmp_path, fake, ["items"], origins={"wikidata"})
    assert [d["entity"] for d in rep.claims_deferred] == ["Q202"]
    assert "not in the target yet" in rep.claims_deferred[0]["reason"]
    _, _, rep2 = run_phases(source_dir, tmp_path, fake, ["items"], origins={"open-archaeo"})
    assert rep2.claims_deferred == []
    tool_c = next(e for e in fake.entities.values() if e["labels"]["en"]["value"] == "Tool C")
    assert tool_c["claims"]["P11"][0]["mainsnak"]["datavalue"]["value"]["id"].startswith("Q")


def test_items_limit_and_third_run_is_quiet(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    _, _, rep = run_phases(source_dir, tmp_path, fake, ["items"], origins={"open-archaeo"}, limit=1)
    assert len(rep.created) == 1
    n = fake.writes
    run_phases(source_dir, tmp_path, fake, ["items"], origins={"open-archaeo"}, limit=1)
    assert fake.writes == n


def test_lost_state_is_rebuilt_from_the_target_without_duplicates(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    (tmp_path / "state-test.json").unlink()
    before = {k: sum(len(v) for v in e["claims"].values()) for k, e in fake.entities.items()}
    _, _, rep = run_phases(source_dir, tmp_path, fake, ["core", "model"])
    after = {k: sum(len(v) for v in e["claims"].values()) for k, e in fake.entities.items()}
    assert before == after and rep.claims_written == 0 and rep.claims_present > 0


def test_dry_run_after_a_real_run_reports_zero_writes(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core", "model"])
    _, _, rep = run_phases(source_dir, tmp_path, None, ["core", "model"], dry_run=True)
    assert rep.calls == [] and rep.claims_written == 0 and len(rep.skipped) == 17


def test_failed_entity_is_reported_and_the_run_continues(source_dir, tmp_path):
    fake = FakeWikibase()
    run_phases(source_dir, tmp_path, fake, ["core"])
    fake.fail_labels = {"chublet"}
    _, pusher, rep = run_phases(source_dir, tmp_path, fake, ["model"])
    assert any("Q101" in f for f in rep.failed_entities)
    assert "P100" in pusher.idmap.map                          # later entities still went through
