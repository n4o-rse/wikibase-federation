"""Unit tests for qs_parser (no network required)."""

from pathlib import Path

import pytest

from wbqs.parser import (
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


# -- datatype column (url / string / external-id) ----------------------------


def test_url_value_is_literal_string(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\twd:P2888\thttps://database.factgrid.de/entity/Q1000294\turl\n", encoding="utf-8")
    st = parse_qs_file(f)[0]
    assert st.value_datatype == "url"
    assert st.value_api == "https://database.factgrid.de/entity/Q1000294"
    assert st.is_federated_value is False        # a url literal is not a federated item
    assert st.is_federated_property is True


def test_external_id_value(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\tP8\tgares_1\texternal-id\n", encoding="utf-8")
    st = parse_qs_file(f)[0]
    assert st.value_datatype == "external-id"
    assert st.value_api == "gares_1"


def test_three_column_item_still_default(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\twd:P31\thttp://www.wikidata.org/entity/Q2016147\n", encoding="utf-8")
    st = parse_qs_file(f)[0]
    assert st.value_datatype == "wikibase-item"
    assert isinstance(st.value_api, dict)
    assert st.is_federated_value is True


def test_unknown_datatype_raises(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\tP8\tfoo\tquantity\n", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_qs_file(f)


def test_coordinate_value(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\twd:P625\t51.893659,-8.492443\tcoordinate\n", encoding="utf-8")
    st = parse_qs_file(f)[0]
    assert st.value_datatype == "globe-coordinate"
    assert st.value_api["latitude"] == pytest.approx(51.893659)
    assert st.value_api["longitude"] == pytest.approx(-8.492443)
    assert st.value_api["globe"].endswith("Q2")


def test_monolingual_value(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\twd:P1684\tCASSITTAS MAQI MUCOI CALLITI\tmonolingual@mul\n", encoding="utf-8")
    st = parse_qs_file(f)[0]
    assert st.value_datatype == "monolingual"
    assert st.value_api == {"text": "CASSITTAS MAQI MUCOI CALLITI", "language": "mul"}


def test_monolingual_without_language_raises(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\twd:P1684\tsome text\tmonolingual\n", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_qs_file(f)


def test_bad_coordinate_raises(tmp_path: Path):
    f = tmp_path / "in.qs"
    f.write_text("Q5\twd:P625\tnot,coords\tcoordinate\n", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_qs_file(f)