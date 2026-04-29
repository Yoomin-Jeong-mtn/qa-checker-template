import pytest
from pathlib import Path
from scripts.load_spec import load_spec

SPECS_DIR = Path(__file__).parent / "fixtures" / "specs"


def test_load_returns_dict_keyed_by_event_name():
    spec = load_spec(str(SPECS_DIR))
    assert "pdp_view" in spec


def test_extends_merges_common_properties():
    spec = load_spec(str(SPECS_DIR))
    pdp = spec["pdp_view"]
    assert "platform" in pdp
    assert "review_score" in pdp


def test_property_def_has_correct_type():
    spec = load_spec(str(SPECS_DIR))
    assert spec["pdp_view"]["platform"]["type"] == "string"
    assert spec["pdp_view"]["platform"]["enum"] == ["PC", "ANDROID_APP", "IOS_APP", "MW"]


def test_event_specific_props_are_included():
    spec = load_spec(str(SPECS_DIR))
    assert spec["pdp_view"]["is_logged_in"]["type"] == "boolean"


def test_unknown_event_not_in_spec():
    spec = load_spec(str(SPECS_DIR))
    assert "unknown_event" not in spec
