#!/usr/bin/env python3
"""Ask the query service of chublets-wikibase.de how the pushed data looks, read only.

    python usecases\\chublets\\query_check.py
    python usecases\\chublets\\query_check.py --endpoint https://query.chublets-wikibase.de/proxy/wdqs/bigdata/namespace/wdq/sparql
    python usecases\\chublets\\query_check.py --item Q811 --out usecases\\chublets\\report\\before

What it does, in this order (nothing is written to the wiki, only ``usecases/chublets/report/query-service-<date>.md`` and ``.json``, git-ignored):

1. finds the SPARQL endpoint (the ``--endpoint`` or the usual paths below ``https://query.chublets-wikibase.de``);
2. finds the IRI of the item (default Q811 = Alligator, source Q359) by its English label from the idmap and derives
   the concept base and the ``wdt:`` prefix of this wiki from it, so nothing is guessed;
3. dumps all direct claims of the item and sorts every object into *federated* (``http://www.wikidata.org/entity/Q...``,
   what the push writes for ``wikidata-stub`` items), *local* (an item of this wiki) or *literal*;
4. asks the label service for the developers (``P113`` of the source, ``P24`` here): does it name the federated Wikidata
   values or only return their ids?
5. counts the chublets (``instance of`` -> ``chublet``) and the tools per topic (``main subject`` -> Q116 / Q126 of the source)
   and compares them with the numbers the push reports (439 before ``--prune``, 420 after).

Needs only the standard library. The script cannot be tried from the sandbox that wrote it (the host is not reachable there),
it is tested against a local fake server only: read the report, not the exit code, to know how the live service behaves.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_HOST = "https://query.chublets-wikibase.de"
ENDPOINT_PATHS = ("/proxy/wdqs/bigdata/namespace/wdq/sparql", "/bigdata/namespace/wdq/sparql", "/sparql")
WIKIDATA_ENTITY = "http://www.wikidata.org/entity/"
USER_AGENT = "wikibase-federation-query-check/1.3.1 (https://github.com/florianthiery/wikibase-federation)"

# source ids (CSV model) that the check needs; the target ids come from the idmap
SRC_CHUBLET, SRC_INSTANCE_OF, SRC_DEVELOPER, SRC_MAIN_SUBJECT = "Q106", "P2", "P113", "P117"
SRC_TOPICS = {"Q116": "Statistical analysis", "Q126": "Chronological modelling"}
EXPECTED = {"before_prune": 439, "after_prune": 420}


class QueryError(RuntimeError):
    pass


class Sparql:
    def __init__(self, endpoint: str, timeout: float = 60.0) -> None:
        self.endpoint, self.timeout = endpoint, timeout

    def select(self, query: str) -> list[dict[str, dict]]:
        data = urllib.parse.urlencode({"query": query}).encode()
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise QueryError(f"HTTP {exc.code} from {self.endpoint}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise QueryError(f"cannot reach {self.endpoint}: {exc}") from exc
        try:
            return json.loads(body)["results"]["bindings"]
        except (ValueError, KeyError) as exc:
            raise QueryError(f"{self.endpoint} did not answer with SPARQL JSON: {body[:200]!r}") from exc


def find_endpoint(host: str, explicit: str | None) -> Sparql:
    candidates = [explicit] if explicit else [host.rstrip("/") + p for p in ENDPOINT_PATHS]
    errors = []
    for url in candidates:
        client = Sparql(url)
        try:
            client.select("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            return client
        except QueryError as exc:
            errors.append(str(exc))
    raise QueryError("no SPARQL endpoint answered:\n  " + "\n  ".join(errors))


def read_idmap(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    ids, labels = {}, {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ids[row["source_id"]] = row["target_id"]
            labels[row["source_id"]] = row["label_en"]
    return ids, labels


def value(binding: dict, name: str) -> str | None:
    return binding[name]["value"] if name in binding else None


def classify(obj: dict, base: str) -> str:
    if obj.get("type") != "uri":
        return "literal"
    iri = obj["value"]
    if iri.startswith(WIKIDATA_ENTITY):
        return "federated (wikidata entity IRI)"
    if iri.startswith(base + "/entity/"):
        return "local item"
    return "other IRI"


def run(args: argparse.Namespace, now: dt.date) -> tuple[dict, str]:
    ids, labels = read_idmap(Path(args.idmap))
    target_item = args.item
    src_item = next((s for s, t in ids.items() if t == target_item and s.startswith("Q")), None)
    label = labels.get(src_item or "", "")
    result: dict = {"retrieved": now.isoformat(), "item": target_item, "source_item": src_item, "label": label}

    client = find_endpoint(args.host, args.endpoint)
    result["endpoint"] = client.endpoint

    # 2. the IRI of the item and the prefixes of this wiki
    esc = label.replace("\\", "\\\\").replace('"', '\\"')
    rows = client.select(f'SELECT ?s WHERE {{ ?s <http://www.w3.org/2000/01/rdf-schema#label> "{esc}"@en . }} LIMIT 20')
    hits = [value(r, "s") for r in rows if (value(r, "s") or "").endswith("/entity/" + target_item)]
    if not hits:
        raise QueryError(f"no subject with the label {label!r} ends in /entity/{target_item}; found: {[value(r, 's') for r in rows]}")
    iri = hits[0]
    base = iri.rsplit("/entity/", 1)[0]
    wdt = base + "/prop/direct/"
    result.update(iri=iri, base=base, wdt=wdt)

    # 3. all direct claims, sorted by kind of object
    rows = client.select(f"SELECT ?p ?o WHERE {{ <{iri}> ?p ?o . FILTER(STRSTARTS(STR(?p), \"{wdt}\")) }}")
    claims = []
    for r in rows:
        pid = value(r, "p")[len(wdt):]
        claims.append({"property": pid, "kind": classify(r["o"], base), "type": r["o"].get("type"), "datatype": r["o"].get("datatype"), "value": value(r, "o")})
    claims.sort(key=lambda c: (int(c["property"][1:]) if c["property"][1:].isdigit() else 0, c["value"] or ""))
    result["claims"] = claims
    kinds: dict[str, int] = {}
    for c in claims:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    result["claim_kinds"] = kinds

    # 4. label service on the developers
    dev = ids.get(SRC_DEVELOPER)
    result["developer_property"] = dev
    result["developers"] = []
    if dev:
        rows = client.select(
            f'SELECT ?o ?oLabel WHERE {{ <{iri}> <{wdt}{dev}> ?o . SERVICE <http://wikiba.se/ontology#label> {{ <http://www.bigdata.com/rdf#serviceParam> <http://wikiba.se/ontology#language> "en" . }} }}'
        )
        for r in rows:
            o, lab = value(r, "o"), value(r, "oLabel")
            named = bool(lab) and lab != (o or "").rsplit("/", 1)[-1] and lab != o
            result["developers"].append({"object": o, "label": lab, "label_service_names_it": named})

    # 5. counts
    inst, chub = ids.get(SRC_INSTANCE_OF), ids.get(SRC_CHUBLET)
    counts: dict[str, object] = {}
    if inst and chub:
        rows = client.select(f"SELECT (COUNT(DISTINCT ?t) AS ?n) WHERE {{ ?t <{wdt}{inst}> <{base}/entity/{chub}> . }}")
        counts["chublets"] = int(value(rows[0], "n"))
    subj = ids.get(SRC_MAIN_SUBJECT)
    for topic, name in SRC_TOPICS.items():
        tid = ids.get(topic)
        if subj and tid and inst and chub:
            rows = client.select(
                f"SELECT (COUNT(DISTINCT ?t) AS ?n) WHERE {{ ?t <{wdt}{inst}> <{base}/entity/{chub}> ; <{wdt}{subj}> <{base}/entity/{tid}> . }}"
            )
            counts[f"{topic}_tools"] = int(value(rows[0], "n"))
            counts[f"{topic}_name"] = name
    result["counts"] = counts
    return result, render(result)


def render(r: dict) -> str:
    out = [f"# Query service check, {r['retrieved']}", ""]
    out += [f"* endpoint: `{r['endpoint']}`", f"* item: `{r['item']}` = {r['label']} (source `{r['source_item']}`)", f"* IRI: `{r['iri']}`", f"* `wdt:` prefix of this wiki: `{r['wdt']}`", ""]
    out += ["## Direct claims of the item", "", "| property | kind of object | value |", "|---|---|---|"]
    out += [f"| {c['property']} | {c['kind']} | `{c['value']}` |" for c in r["claims"]]
    out += ["", "Summary: " + ", ".join(f"{k}: {v}" for k, v in sorted(r["claim_kinds"].items())), ""]
    out += [f"## Developers ({r['developer_property']}) and the label service", ""]
    if r["developers"]:
        out += ["| object | label | label service names it |", "|---|---|---|"]
        out += [f"| `{d['object']}` | {d['label'] or '-'} | {'yes' if d['label_service_names_it'] else 'no, only the id'} |" for d in r["developers"]]
    else:
        out += ["no developer claims returned."]
    out += ["", "## Counts", ""]
    c = r["counts"]
    if "chublets" in c:
        verdict = {EXPECTED["before_prune"]: "the state before `--prune`", EXPECTED["after_prune"]: "the state after `--prune`"}.get(c["chublets"], "neither 439 (before `--prune`) nor 420 (after)")
        out += [f"* chublets (instance of chublet): **{c['chublets']}**, {verdict}"]
    for topic in SRC_TOPICS:
        if f"{topic}_tools" in c:
            out += [f"* tools with main subject {c[f'{topic}_name']} ({topic} of the source): **{c[f'{topic}_tools']}**"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default=DEFAULT_HOST, help="base URL of the query service")
    parser.add_argument("--endpoint", help="full SPARQL endpoint URL (skips the search over the usual paths)")
    parser.add_argument("--item", default="Q811", help="target id of the item to look at (default Q811 = Alligator)")
    parser.add_argument("--idmap", default=str(HERE / "idmap-chublets-wikibase.de.csv"))
    parser.add_argument("--out", default=str(HERE / "report"), help="folder for the report (default usecases/chublets/report, git-ignored)")
    parser.add_argument("--retrieved", help="date for the file name, YYYY-MM-DD (default: today)")
    args = parser.parse_args(argv)
    now = dt.date.fromisoformat(args.retrieved) if args.retrieved else dt.date.today()
    try:
        result, text = run(args, now)
    except QueryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # Path.write_text(newline=...) needs Python 3.10; the CI also runs 3.9
    for suffix, content in (("md", text), ("json", json.dumps(result, indent=2, ensure_ascii=False) + "\n")):
        with (out / f"query-service-{now.isoformat()}.{suffix}").open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    print(text)
    print(f"written: {out / ('query-service-' + now.isoformat() + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
