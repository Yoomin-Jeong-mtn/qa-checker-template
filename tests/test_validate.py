import pytest
from scripts.validate import validate

SPEC = {
    "pdp_view": {
        "platform": {"key": "platform", "type": "string", "required": True, "enum": ["PC", "MW"], "allow_empty": False},
        "is_logged_in": {"key": "is_logged_in", "type": "boolean", "required": True, "allow_empty": False},
        "review_score": {"key": "review_score", "type": "number", "required": True, "allow_empty": False},
        "detail_category_name": {"key": "detail_category_name", "type": "string", "required": True, "allow_empty": True},
    }
}

def make_row(event_id="evt_001", name="pdp_view", props=None):
    return {
        "row": 2, "name": name, "time": "1776064118",
        "user_id": "user_abc", "event_id": event_id,
        "properties": props or {
            "platform": "PC", "is_logged_in": True,
            "review_score": 4.5, "detail_category_name": "",
        }
    }


def test_valid_row_produces_no_violations():
    result = validate([make_row()], SPEC)
    assert result["violations"] == []
    assert result["unknowns"] == []


def test_enum_mismatch_is_violation():
    row = make_row(props={"platform": "WEB", "is_logged_in": True, "review_score": 4.5, "detail_category_name": ""})
    result = validate([row], SPEC)
    v = result["violations"][0]
    assert v["error_type"] == "enum_mismatch"
    assert v["key"] == "platform"
    assert v["event_id"] == "evt_001"


def test_type_mismatch_is_violation():
    row = make_row(props={"platform": "PC", "is_logged_in": True, "review_score": "not_a_number", "detail_category_name": ""})
    result = validate([row], SPEC)
    v = result["violations"][0]
    assert v["error_type"] == "type_mismatch"
    assert v["key"] == "review_score"


def test_missing_required_prop_is_violation():
    row = make_row(props={"platform": "PC", "is_logged_in": True, "detail_category_name": ""})
    result = validate([row], SPEC)
    keys = [v["key"] for v in result["violations"]]
    assert "review_score" in keys


def test_empty_string_allowed_when_allow_empty_true():
    row = make_row(props={"platform": "PC", "is_logged_in": True, "review_score": 4.5, "detail_category_name": ""})
    result = validate([row], SPEC)
    assert result["violations"] == []


def test_unknown_property_goes_to_unknowns():
    row = make_row(props={"platform": "PC", "is_logged_in": True, "review_score": 4.5, "detail_category_name": "", "mystery_prop": 42})
    result = validate([row], SPEC)
    assert result["unknowns"][0]["key"] == "mystery_prop"
    assert 42 in result["unknowns"][0]["sample_values"]


def test_unknown_event_goes_to_unknowns():
    row = make_row(name="checkout_complete", props={"platform": "PC"})
    result = validate([row], SPEC)
    assert result["unknowns"][0]["event_name"] == "checkout_complete"
    assert result["unknowns"][0]["key"] is None


def test_unknowns_are_deduplicated():
    rows = [
        make_row(event_id="e1", props={"platform": "PC", "is_logged_in": True, "review_score": 4.5, "detail_category_name": "", "new_prop": "a"}),
        make_row(event_id="e2", props={"platform": "PC", "is_logged_in": True, "review_score": 4.5, "detail_category_name": "", "new_prop": "b"}),
    ]
    result = validate(rows, SPEC)
    new_prop_unknowns = [u for u in result["unknowns"] if u["key"] == "new_prop"]
    assert len(new_prop_unknowns) == 1
    assert len(new_prop_unknowns[0]["sample_values"]) == 2


def test_total_rows_count():
    result = validate([make_row(), make_row(event_id="e2")], SPEC)
    assert result["total_rows"] == 2
