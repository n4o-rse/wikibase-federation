"""Unit tests for qs_parser (no network required)."""

from pathlib import Path

import pytest

from qs_parser import (
    WIKIDATA_ENTITY_PREFIX,
    ParseError,
    parse_qs_file,
    parse_value,
)


def test_local_qid_default():
    assert parse_value("Q4") == {"entity-type": "item", "id": "Q4"}


def test_local_qid_lowercase_normalised():
    assert parse_value("q4") == {"entity-type": "item", "id": "Q4"}


def test_wd_prefix_is_federated():
    assert parse_value("wd:Q2016147") == {
        "entity-type": "item",
        "id": f"{WIKIDATA_ENTITY_PREFIX}Q2016147",
    }


def test_full_uri_is_federated():
    assert parse_value("http://www.wikidata.org/entity/Q2016147") == {
        "entity-type": "item",
        "id": f"{WIKIDATA_ENTITY_PREFIX}Q2016147",
    }


def test_https_uri_normalised_to_http_prefix():
    result = parse_value("https://www.wikidata.org/entity/Q42")
    assert result["id"] == f"{WIKIDATA_ENTITY_PREFIX}Q42"


def test_bare_qid_federated_when_flag_set():
    assert parse_value("Q5", federate_bare_qids=True) == {
        "entity-type": "item",
        "id": f"{WIKIDATA_ENTITY_PREFIX}Q5",
    }


def test_quotes_are_stripped():
    assert parse_value('"Q4"') == {"entity-type": "item", "id": "Q4"}


@pytest.mark.parametrize("bad", ["", "P1", "Q0", "Q01", "foo", "wd:P1", "42"])
def test_unsupported_values_raise(bad):
    with pytest.raises(ParseError):
        parse_value(bad)


def test_parse_file_skips_comments_and_blanks(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text(
        "# comment\n"
        "\n"
        "Q3\tP1\tQ4\n"
        "Q3\tP1\thttp://www.wikidata.org/entity/Q2016147\n"
        "Q3 P1 wd:Q5\n",  # whitespace separated
        encoding="utf-8",
    )
    statements = parse_qs_file(f)
    assert len(statements) == 3
    assert statements[0].entity == "Q3"
    assert statements[0].prop == "P1"
    assert statements[0].is_federated is False
    assert statements[1].is_federated is True
    assert statements[2].is_federated is True


def test_parse_file_reports_bad_line(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q3\tP1\n", encoding="utf-8")  # only 2 columns
    with pytest.raises(ParseError) as exc:
        parse_qs_file(f)
    assert "Line 1" in str(exc.value)


def test_parse_file_rejects_bad_property(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q3\tX1\tQ4\n", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_qs_file(f)
