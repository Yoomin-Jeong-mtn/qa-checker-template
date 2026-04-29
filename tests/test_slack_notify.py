import pytest
from unittest.mock import patch, MagicMock
from scripts.slack_notify import format_message, send_to_slack

RESULTS = {
    "violations": [
        {"event_id": "evt_001", "event_name": "pdp_view", "key": "platform",
         "value": "WEB", "error_type": "enum_mismatch", "error_detail": "허용값 아님 (enum: PC|MW)"},
    ],
    "unknowns": [],
    "total_rows": 10,
}

INFERENCE = []


def test_format_message_contains_filename():
    msgs = format_message(RESULTS, "pdp_view_20260417.csv", INFERENCE)
    assert any("pdp_view_20260417.csv" in m for m in msgs)


def test_format_message_contains_violation_event_id():
    msgs = format_message(RESULTS, "test.csv", INFERENCE)
    full = "\n".join(msgs)
    assert "evt_001" in full


def test_format_message_contains_pass_count():
    msgs = format_message(RESULTS, "test.csv", INFERENCE)
    full = "\n".join(msgs)
    assert "✅" in full


def test_long_message_is_split():
    large_results = {
        "violations": [
            {"event_id": f"evt_{i:04d}", "event_name": "pdp_view", "key": "platform",
             "value": "WEB", "error_type": "enum_mismatch", "error_detail": "허용값 아님 (enum: PC|MW)"}
            for i in range(200)
        ],
        "unknowns": [],
        "total_rows": 200,
    }
    msgs = format_message(large_results, "large.csv", [])
    assert len(msgs) > 1
    for msg in msgs:
        assert len(msg) <= 3000


def test_send_to_slack_posts_each_chunk():
    msgs = ["chunk1", "chunk2"]
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("scripts.slack_notify.requests.post", return_value=mock_response) as mock_post:
        send_to_slack("https://hooks.slack.com/test", msgs)
        assert mock_post.call_count == 2


def test_inference_items_in_message():
    inference = [{"event_name": "pdp_view", "key": "new_prop", "inferred_type": "string", "inferred_required": False}]
    msgs = format_message({"violations": [], "unknowns": [], "total_rows": 5}, "test.csv", inference)
    full = "\n".join(msgs)
    assert "new_prop" in full
    assert "🔍" in full
