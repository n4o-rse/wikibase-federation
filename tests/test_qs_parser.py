"""Unit tests for qs_parser (no network required)."""

from pathlib import Path

import pytest

from qs_parser import (
    WIKIDATA_ENTITY_PREFIX,
    ParseError,
    parse_property,
    parse_qs_file,
    parse_value,
)

WD = WIKIDATA_ENTITY_PREFIX


# -- values ------------------------------------------------------------------


def test_local_qid_default():
    assert parse_value("Q4") == {"entity-type": "item", "id": "Q4"}


def test_local_qid_lowercase_normalised():
    assert parse_value("q4") == {"entity-type": "item", "id": "Q4"}


def test_wd_prefix_value_is_federated():
    assert parse_value("wd:Q2016147") == {"entity-type": "item", "id": f"{WD}Q2016147"}


def test_full_item_uri_is_federated():
    assert parse_value("http://www.wikidata.org/entity/Q2016147") == {
        "entity-type": "item",
        "id": f"{WD}Q2016147",
    }


def test_https_item_uri_normalised_to_http_prefix():
    assert parse_value("https://www.wikidata.org/entity/Q42")["id"] == f"{WD}Q42"


def test_bare_qid_federated_when_flag_set():
    assert parse_value("Q5", federate_bare_qids=True) == {"entity-type": "item", "id": f"{WD}Q5"}


def test_value_quotes_are_stripped():
    assert parse_value('"Q4"') == {"entity-type": "item", "id": "Q4"}


@pytest.mark.parametrize("bad", ["", "P1", "Q0", "Q01", "foo", "wd:P1", "42"])
def test_unsupported_values_raise(bad):
    with pytest.raises(ParseError):
        parse_value(bad)


# -- properties --------------------------------------------------------------


def test_local_pid():
    assert parse_property("P1") == "P1"


def test_local_pid_lowercase_normalised():
    assert parse_property("p7") == "P7"


def test_wd_prefix_property_is_federated():
    assert parse_property("wd:P5572") == f"{WD}P5572"


def test_wdt_prefix_property_normalised_to_entity_uri():
    assert parse_property("wdt:P5572") == f"{WD}P5572"


def test_property_entity_uri():
    assert parse_property("http://www.wikidata.org/entity/P5572") == f"{WD}P5572"


def test_property_direct_uri_normalised():
    assert parse_property("http://www.wikidata.org/prop/direct/P5572") == f"{WD}P5572"


def test_bare_pid_federated_when_flag_set():
    assert parse_property("P5572", federate_bare_pids=True) == f"{WD}P5572"


@pytest.mark.parametrize("bad", ["", "Q1", "wd:Q5", "foo", "P0", "5572"])
def test_unsupported_properties_raise(bad):
    with pytest.raises(ParseError):
        parse_property(bad)


# -- whole file / four combinations ------------------------------------------


def test_parse_file_all_four_combinations(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text(
        "# comment\n"
        "\n"
        "Q3\tP1\tQ4\n"                                    # local prop + local val
        "Q3\tP1\thttp://www.wikidata.org/entity/Q5\n"     # local prop + fed val
        "Q3\twd:P5572\tQ4\n"                              # fed prop + local val
        "Q3 wd:P5572 wd:Q5\n",                            # fed prop + fed val (ws sep)
        encoding="utf-8",
    )
    st = parse_qs_file(f)
    assert len(st) == 4

    assert (st[0].is_federated_property, st[0].is_federated_value) == (False, False)
    assert (st[1].is_federated_property, st[1].is_federated_value) == (False, True)
    assert (st[2].is_federated_property, st[2].is_federated_value) == (True, False)
    assert (st[3].is_federated_property, st[3].is_federated_value) == (True, True)

    # federated property is sent as the entity URI
    assert st[2].prop == f"{WD}P5572"
    assert st[2].value_api == {"entity-type": "item", "id": "Q4"}
    assert st[3].value_api == {"entity-type": "item", "id": f"{WD}Q5"}

    # backwards-compatible alias still works
    assert st[1].is_federated is True


def test_subject_must_be_local(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("wd:Q5\tP1\tQ4\n", encoding="utf-8")
    with pytest.raises(ParseError) as exc:
        parse_qs_file(f)
    assert "subject must be a LOCAL item" in str(exc.value)


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