import json
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_format_pace_correct():
    from scripts.normalize import format_pace
    assert format_pace(10400, 3120) == "5:00"


def test_format_pace_handles_zero():
    from scripts.normalize import format_pace
    assert format_pace(0, 3120) is None
    assert format_pace(10400, 0) is None


def test_compute_km_splits_basic():
    from scripts.normalize import compute_km_splits
    streams = {
        "time":     [0, 234, 469, 704, 939, 1174, 1409, 1644, 1879, 2114, 2349],
        "distance": [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        "heartrate": [132, 145, 158, 162, 165, 168, 170, 167, 164, 162, 160],
        "cadence":  [172, 176, 180, 182, 181, 183, 182, 181, 180, 179, 178],
    }
    splits = compute_km_splits(streams)
    assert len(splits) == 10
    assert splits[0]["km"] == 1
    assert splits[0]["pace"] is not None
    assert splits[0]["hr"] is not None
    assert splits[0]["cadence"] is not None


def test_compute_km_splits_empty():
    from scripts.normalize import compute_km_splits
    assert compute_km_splits({}) == []
    assert compute_km_splits({"distance": [], "time": []}) == []


def test_build_snapshot_wellness():
    from scripts.normalize import build_snapshot
    raw_intervals = {
        "date": "2026-04-17",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": [],
    }
    garmin = load_fixture("garmin_raw.json")
    snap = build_snapshot(raw_intervals, garmin)

    w = snap["wellness"]
    assert snap["date"] == "2026-04-17"
    assert w["hrv_avg_ms"] == 52
    assert w["hrv_5min_high_ms"] == 61
    assert w["rhr"] == 49
    assert w["ctl"] == 31.2
    assert w["atl"] == 47.1
    assert w["tsb"] == pytest.approx(-15.9, abs=0.1)
    assert w["weight"] == 93.0
    assert w["steps"] == 11240
    assert w["calories_active"] == 820


def test_build_snapshot_sleep():
    from scripts.normalize import build_snapshot
    raw_intervals = {
        "date": "2026-04-17",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": [],
    }
    garmin = load_fixture("garmin_raw.json")
    snap = build_snapshot(raw_intervals, garmin)

    sleep = snap["wellness"]["sleep"]
    assert sleep["total_h"] == 7.2
    assert sleep["score"] == 78
    assert sleep["phases_h"]["deep"] == 1.53
    assert sleep["phases_h"]["rem"] == 1.23
    assert sleep["bedtime"] == "23:18"


def test_build_snapshot_run_activity():
    from scripts.normalize import build_snapshot
    raw_intervals = {
        "date": "2026-04-17",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": load_fixture("intervals_activities.json"),
    }
    garmin = load_fixture("garmin_raw.json")
    snap = build_snapshot(raw_intervals, garmin)

    assert len(snap["activities"]) == 1
    run = snap["activities"][0]
    assert run["type"] == "Run"
    assert run["distance_km"] == 10.4
    assert run["avg_pace"] == "5:00"
    assert run["avg_hr"] == 162.0
    assert run["tss"] == 94
    assert run["interval_summary"] is not None
    assert run["hr_zone_times_s"] is not None


def test_build_snapshot_run_has_km_splits():
    from scripts.normalize import build_snapshot
    raw_intervals = {
        "date": "2026-04-17",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": load_fixture("intervals_activities.json"),
    }
    garmin = load_fixture("garmin_raw.json")
    snap = build_snapshot(raw_intervals, garmin)

    run = snap["activities"][0]
    assert "km_splits" in run
    assert len(run["km_splits"]) == 10
    assert run["km_splits"][0]["km"] == 1


def test_build_snapshot_strength_activity():
    from scripts.normalize import build_snapshot
    raw_intervals = {
        "date": "2026-04-15",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": [load_fixture("intervals_activity_detail.json")],
    }
    snap = build_snapshot(raw_intervals, None)

    gym = snap["activities"][0]
    assert gym["type"] == "Strength"
    assert gym["kg_lifted"] == 16844.0
    assert gym["avg_hr"] == 108.0


def test_build_snapshot_no_garmin():
    from scripts.normalize import build_snapshot
    raw_intervals = {
        "date": "2026-04-17",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": [],
    }
    snap = build_snapshot(raw_intervals, None)
    assert snap["wellness"]["steps"] is None
    assert snap["wellness"]["sleep"]["total_h"] is None
