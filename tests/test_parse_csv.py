import json
import pytest
from pathlib import Path
from scripts.parse_csv import parse_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"


def test_parse_returns_list_of_rows():
    rows = parse_csv(str(FIXTURE))
    assert isinstance(rows, list)
    assert len(rows) == 4


def test_row_has_required_fields():
    rows = parse_csv(str(FIXTURE))
    row = rows[0]
    assert row["name"] == "pdp_view"
    assert row["event_id"] == "evt_001"
    assert isinstance(row["properties"], dict)


def test_properties_are_parsed_as_dict():
    rows = parse_csv(str(FIXTURE))
    props = rows[0]["properties"]
    assert props["platform"] == "PC"
    assert props["is_logged_in"] is True
    assert props["review_score"] == 4.5


def test_row_number_starts_at_2():
    rows = parse_csv(str(FIXTURE))
    assert rows[0]["row"] == 2
