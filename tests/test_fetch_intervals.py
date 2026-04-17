import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURES = Path(__file__).parent / "fixtures"


def mock_response(fixture_name):
    data = json.loads((FIXTURES / fixture_name).read_text())
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_wellness(mock_get):
    from scripts.fetch_intervals import fetch_wellness
    mock_get.return_value = mock_response("intervals_wellness.json")

    result = fetch_wellness("i464516", "my_key", "2026-04-17")

    assert result["id"] == "2026-04-17"
    assert result["restingHR"] == 49
    assert result["ctl"] == 31.2
    url = mock_get.call_args[0][0]
    assert "wellness/2026-04-17" in url


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_activities(mock_get):
    from scripts.fetch_intervals import fetch_activities
    mock_get.return_value = mock_response("intervals_activities.json")

    result = fetch_activities("i464516", "my_key", "2026-04-17")

    assert len(result) == 1
    assert result[0]["type"] == "Run"
    assert result[0]["distance"] == 10400


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_activity_detail(mock_get):
    from scripts.fetch_intervals import fetch_activity_detail
    mock_get.return_value = mock_response("intervals_activity_detail.json")

    result = fetch_activity_detail("i140056165", "my_key")

    assert result["type"] == "WeightTraining"
    assert result["kg_lifted"] == 16844.0


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_wellness_401_exits(mock_get):
    from scripts.fetch_intervals import fetch_wellness
    mock = MagicMock()
    mock.status_code = 401
    mock_get.return_value = mock

    with pytest.raises(SystemExit):
        fetch_wellness("i464516", "bad_key", "2026-04-17")
