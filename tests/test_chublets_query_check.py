"""Tests of usecases/chublets/query_check.py against a local fake SPARQL server (the live service was not reachable)."""

from __future__ import annotations

import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "usecases" / "chublets"))

import query_check as qc  # noqa: E402

IDMAP = (
    "source_id,target_id,label_en\n"
    "P2,P1,instance of\nP113,P24,developer\nP117,P30,main subject\n"
    "Q106,Q1,chublet\nQ116,Q60,Statistical analysis\nQ126,Q70,Chronological modelling\nQ359,Q811,Alligator - Allen Transformer\n"
)
BASE = "https://chublets-wikibase.de"
ITEM = f"{BASE}/entity/Q811"


def uri(v):
    return {"type": "uri", "value": v}


class Handler(BaseHTTPRequestHandler):
    chublets = 439
    named = False
    log: list[str] = []

    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        query = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())["query"][0]
        Handler.log.append(query)
        if not self.path.endswith("/proxy/wdqs/bigdata/namespace/wdq/sparql"):
            self.send_response(404)
            self.end_headers()
            return
        rows: list[dict] = []
        if "rdf-schema#label" in query:
            rows = [{"s": uri(ITEM)}]
        elif "STRSTARTS" in query:
            rows = [
                {"p": uri(f"{BASE}/prop/direct/P24"), "o": uri("http://www.wikidata.org/entity/Q1234")},
                {"p": uri(f"{BASE}/prop/direct/P1"), "o": uri(f"{BASE}/entity/Q1")},
                {"p": uri(f"{BASE}/prop/direct/P99"), "o": {"type": "literal", "value": "text"}},
            ]
        elif "serviceParam" in query:
            rows = [{"o": uri("http://www.wikidata.org/entity/Q1234"), "oLabel": {"type": "literal", "value": "Q1234" if not Handler.named else "Jane Doe"}}]
        elif "COUNT" in query:
            n = Handler.chublets if f"/entity/Q60" not in query and "/entity/Q70" not in query else 7
            rows = [{"n": {"type": "literal", "value": str(n)}}]
        elif re.search(r"LIMIT 1\b", query):
            rows = [{"s": uri("a"), "p": uri("b"), "o": uri("c")}]
        body = json.dumps({"head": {}, "results": {"bindings": rows}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/sparql-results+json")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def server(tmp_path):
    Handler.chublets, Handler.named, Handler.log = 439, False, []
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    idmap = tmp_path / "idmap.csv"
    idmap.write_text(IDMAP, encoding="utf-8")
    yield f"http://127.0.0.1:{httpd.server_port}", idmap, tmp_path
    httpd.shutdown()


def test_the_endpoint_is_found_among_the_usual_paths_and_the_report_is_written(server, capsys):
    host, idmap, tmp = server
    code = qc.main(["--host", host, "--idmap", str(idmap), "--out", str(tmp / "report"), "--retrieved", "2026-11-03"])
    assert code == 0
    data = json.loads((tmp / "report" / "query-service-2026-11-03.json").read_text(encoding="utf-8"))
    assert data["endpoint"].endswith("/proxy/wdqs/bigdata/namespace/wdq/sparql")
    assert data["wdt"] == f"{BASE}/prop/direct/" and data["iri"] == ITEM
    assert (tmp / "report" / "query-service-2026-11-03.md").read_text(encoding="utf-8").startswith("# Query service check, 2026-11-03")


def test_objects_are_sorted_into_federated_local_and_literal(server):
    host, idmap, tmp = server
    qc.main(["--host", host, "--idmap", str(idmap), "--out", str(tmp), "--retrieved", "2026-11-03"])
    kinds = json.loads((tmp / "query-service-2026-11-03.json").read_text(encoding="utf-8"))["claim_kinds"]
    assert kinds == {"federated (wikidata entity IRI)": 1, "local item": 1, "literal": 1}


def test_the_label_service_result_is_judged_by_whether_it_names_the_value(server):
    host, idmap, tmp = server
    qc.main(["--host", host, "--idmap", str(idmap), "--out", str(tmp), "--retrieved", "2026-11-03"])
    assert json.loads((tmp / "query-service-2026-11-03.json").read_text(encoding="utf-8"))["developers"][0]["label_service_names_it"] is False
    Handler.named = True
    qc.main(["--host", host, "--idmap", str(idmap), "--out", str(tmp), "--retrieved", "2026-11-04"])
    assert json.loads((tmp / "query-service-2026-11-04.json").read_text(encoding="utf-8"))["developers"][0]["label_service_names_it"] is True


@pytest.mark.parametrize("n, words", [(439, "before `--prune`"), (420, "after `--prune`"), (441, "neither")])
def test_the_chublet_count_is_compared_with_the_expected_numbers(server, n, words):
    host, idmap, tmp = server
    Handler.chublets = n
    qc.main(["--host", host, "--idmap", str(idmap), "--out", str(tmp), "--retrieved", "2026-11-03"])
    text = (tmp / "query-service-2026-11-03.md").read_text(encoding="utf-8")
    assert f"**{n}**" in text and words in text


def test_an_unreachable_service_gives_exit_code_2_and_writes_nothing(tmp_path, capsys):
    idmap = tmp_path / "idmap.csv"
    idmap.write_text(IDMAP, encoding="utf-8")
    code = qc.main(["--endpoint", "http://127.0.0.1:9/sparql", "--idmap", str(idmap), "--out", str(tmp_path / "r")])
    assert code == 2 and not (tmp_path / "r").exists()
    assert "cannot reach" in capsys.readouterr().err
