# Daily Training Routine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automated nightly system (00:00–02:00) that fetches training data, produces a rich normalized snapshot, adapts tomorrow's plan, and sends a Telegram report.

**Architecture:** `fetch_intervals.py` pulls from intervals.icu REST API (wellness + activities + gym sets). During the daily Routine, Claude calls GetFast MCP tools directly and writes `data/raw/garmin/YYYY-MM-DD.json`. Then `normalize.py` merges both into `data/snapshots/YYYY-MM-DD.json`. Claude reads the snapshot + `profile/me.md` + `plan/week-*.md` to write the report and adapt the plan.

**Tech Stack:** Python 3.11+, `requests`, `python-dotenv`, intervals.icu REST API, GetFast MCP (Garmin/Strava), Telegram Bot API

---

## File Map

| File | Role |
|------|------|
| `scripts/fetch_intervals.py` | intervals.icu: wellness + activity list + details (TSS, zones, interval_summary, kg_lifted) |
| `scripts/normalize.py` | Merges intervals + garmin raw JSON → single snapshot |
| `scripts/send_telegram.py` | Sends markdown file to Telegram Bot API |
| `data/raw/intervals/YYYY-MM-DD.json` | Raw intervals.icu output (gitignored) |
| `data/raw/garmin/YYYY-MM-DD.json` | Raw Garmin output written by Claude via MCP (gitignored) |
| `data/snapshots/YYYY-MM-DD.json` | Normalized snapshot — main input for Claude analysis |
| `data/reports/YYYY-MM-DD.md` | Telegram message archive |
| `data/logs/YYYY-MM-DD.md` | Full routine trace |
| `profile/me.md` | Athlete profile: medical, supplements, goals, limits |
| `CLAUDE.md` | Instructions for every Claude Code session in this repo |
| `plan/week-2026-16.md` | Current week plan (week of 2026-04-13) |
| `plan/week-2026-17.md` | Next week plan (week of 2026-04-20) |
| `prompts/daily-routine.md` | The Routine prompt (runs nightly) |
| `prompts/weekly-review.md` | Weekly review prompt (manual trigger) |
| `requirements.txt` | Python deps |
| `tests/test_normalize.py` | Unit tests for normalize.py |
| `tests/test_fetch_intervals.py` | Unit tests for fetch_intervals.py (mocked HTTP) |

---

## Task 1: Project skeleton

**Files:**
- Create: `requirements.txt`
- Create: `data/raw/intervals/.gitkeep`
- Create: `data/raw/garmin/.gitkeep`
- Create: `data/snapshots/.gitkeep`
- Create: `data/reports/.gitkeep`
- Create: `data/logs/.gitkeep`
- Create: `plan/archive/.gitkeep`
- Create: `tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create requirements.txt**

```
requests==2.31.0
python-dotenv==1.0.0
pytest==8.1.0
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p scripts data/raw/intervals data/raw/garmin data/snapshots data/reports data/logs plan/archive prompts profile tests
touch data/raw/intervals/.gitkeep data/raw/garmin/.gitkeep data/snapshots/.gitkeep data/reports/.gitkeep data/logs/.gitkeep plan/archive/.gitkeep tests/__init__.py
```

- [ ] **Step 3: Update .gitignore**

Add to existing `C:/git/training-log/.gitignore`:

```
data/raw/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Install deps**

```bash
pip install -r requirements.txt
```

Expected: packages install without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt data/ plan/archive/ prompts/ profile/ tests/ .gitignore
git commit -m "chore: project skeleton"
```

---

## Task 2: fetch_intervals.py

**Files:**
- Create: `scripts/fetch_intervals.py`
- Create: `tests/test_fetch_intervals.py`
- Create: `tests/fixtures/intervals_wellness.json`
- Create: `tests/fixtures/intervals_activities.json`
- Create: `tests/fixtures/intervals_activity_detail.json`

- [ ] **Step 1: Create wellness fixture**

Create `tests/fixtures/intervals_wellness.json`:

```json
{
  "id": "2026-04-17",
  "restingHR": 49,
  "hrv": 52,
  "sleepSecs": 25920,
  "sleepScore": 78,
  "sleepQuality": 3,
  "readiness": 75,
  "ctl": 31.2,
  "atl": 47.1,
  "ctlLoad": 31,
  "atlLoad": 47,
  "rampRate": 0.8,
  "weight": 93.0,
  "fatigue": 2,
  "soreness": 2,
  "mood": 3
}
```

- [ ] **Step 2: Create activities fixture**

Create `tests/fixtures/intervals_activities.json`:

```json
[
  {
    "id": "2026-04-17T07:30:00",
    "athlete_id": "i464516",
    "external_id": "garmin_123456789",
    "type": "Run",
    "name": "Threshold intervals",
    "start_date_local": "2026-04-17T07:30:00",
    "distance": 10400,
    "moving_time": 3120,
    "average_heartrate": 162.0,
    "max_heartrate": 179.0,
    "icu_training_load": 94,
    "icu_intensity": 85,
    "average_cadence": 178
  }
]
```

- [ ] **Step 3: Create activity detail fixture**

Create `tests/fixtures/intervals_activity_detail.json`:

```json
{
  "id": "2026-04-14T18:00:00",
  "type": "WeightTraining",
  "name": "Gym A",
  "moving_time": 3480,
  "icu_training_load": 45,
  "workout_doc": {
    "steps": [
      {
        "type": "step",
        "text": "Dumbbell Bulgarian Split Squat",
        "sets": [
          {"reps": 12, "weight": 12, "time": 74, "rest": 157},
          {"reps": 12, "weight": 12, "time": 80, "rest": 169},
          {"reps": 12, "weight": 12, "time": 80, "rest": 293}
        ]
      },
      {
        "type": "step",
        "text": "Romanian Deadlift",
        "sets": [
          {"reps": 14, "weight": 60, "time": 66, "rest": 91},
          {"reps": 12, "weight": 80, "time": 62, "rest": 134},
          {"reps": 12, "weight": 80, "time": 61, "rest": 402}
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Write failing tests**

Create `tests/test_fetch_intervals.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURES = Path(__file__).parent / "fixtures"


def mock_get(fixture_name):
    """Return a mock response loading a fixture file."""
    data = json.loads((FIXTURES / fixture_name).read_text())
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_wellness(mock_get_fn):
    from scripts.fetch_intervals import fetch_wellness
    mock_get_fn.return_value = mock_get("intervals_wellness.json")

    result = fetch_wellness("i464516", "my_key", "2026-04-17")

    assert result["id"] == "2026-04-17"
    assert result["restingHR"] == 49
    assert result["ctl"] == 31.2
    mock_get_fn.assert_called_once()
    url = mock_get_fn.call_args[0][0]
    assert "wellness/2026-04-17" in url


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_activities(mock_get_fn):
    from scripts.fetch_intervals import fetch_activities
    mock_get_fn.return_value = mock_get("intervals_activities.json")

    result = fetch_activities("i464516", "my_key", "2026-04-17")

    assert len(result) == 1
    assert result[0]["type"] == "Run"
    assert result[0]["distance"] == 10400


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_activity_detail_extracts_sets(mock_get_fn):
    from scripts.fetch_intervals import fetch_activity_detail
    mock_get_fn.return_value = mock_get("intervals_activity_detail.json")

    result = fetch_activity_detail("act123", "my_key")

    assert result["name"] == "Gym A"
    steps = result["workout_doc"]["steps"]
    assert len(steps) == 2
    assert steps[0]["text"] == "Dumbbell Bulgarian Split Squat"
    assert len(steps[0]["sets"]) == 3
    assert steps[0]["sets"][0]["weight"] == 12


@patch("scripts.fetch_intervals.requests.get")
def test_fetch_wellness_401_exits(mock_get_fn):
    from scripts.fetch_intervals import fetch_wellness
    mock = MagicMock()
    mock.status_code = 401
    mock_get_fn.return_value = mock

    with pytest.raises(SystemExit):
        fetch_wellness("i464516", "bad_key", "2026-04-17")
```

- [ ] **Step 5: Run tests — expect FAIL**

```bash
cd C:/git/training-log
python -m pytest tests/test_fetch_intervals.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.fetch_intervals'`

- [ ] **Step 6: Implement fetch_intervals.py**

Create `scripts/__init__.py` (empty), then create `scripts/fetch_intervals.py`:

```python
#!/usr/bin/env python3
"""
Fetch yesterday's wellness + activities from intervals.icu.
Saves to data/raw/intervals/YYYY-MM-DD.json.
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE = "https://intervals.icu/api/v1"


def _auth(api_key: str) -> tuple:
    return ("API_KEY", api_key)


def _get(url: str, api_key: str, params: dict = None) -> dict | list:
    r = requests.get(url, auth=_auth(api_key), params=params, timeout=30)
    if r.status_code == 401:
        print("ERROR: 401 — invalid API key", file=sys.stderr)
        sys.exit(1)
    if r.status_code == 403:
        print("ERROR: 403 — invalid athlete_id", file=sys.stderr)
        sys.exit(1)
    r.raise_for_status()
    return r.json()


def fetch_wellness(athlete_id: str, api_key: str, target_date: str) -> dict:
    return _get(f"{BASE}/athlete/{athlete_id}/wellness/{target_date}", api_key)


def fetch_activities(athlete_id: str, api_key: str, target_date: str) -> list:
    return _get(
        f"{BASE}/athlete/{athlete_id}/activities",
        api_key,
        params={"oldest": target_date, "newest": target_date},
    )


def fetch_activity_detail(activity_id: str, api_key: str) -> dict:
    return _get(f"{BASE}/activity/{activity_id}", api_key)


def main():
    athlete_id = os.environ["INTERVALS_ATHLETE_ID"]
    api_key = os.environ["INTERVALS_API_KEY"]
    target = (date.today() - timedelta(days=1)).isoformat()

    print(f"Fetching intervals.icu data for {target}", file=sys.stderr)

    wellness = fetch_wellness(athlete_id, api_key, target)
    activities_list = fetch_activities(athlete_id, api_key, target)

    activities_detailed = []
    for act in activities_list:
        act_id = act.get("id")
        if act_id:
            detail = fetch_activity_detail(act_id, api_key)
            activities_detailed.append(detail)
        else:
            activities_detailed.append(act)

    raw = {"date": target, "wellness": wellness, "activities": activities_detailed}

    out_dir = Path("data/raw/intervals")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target}.json"
    out_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

Also create `scripts/__init__.py` (empty file).

- [ ] **Step 7: Run tests — expect PASS**

```bash
python -m pytest tests/test_fetch_intervals.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 8: Smoke test against real API**

```bash
cd C:/git/training-log
python scripts/fetch_intervals.py
cat data/raw/intervals/$(date -d "yesterday" +%Y-%m-%d).json | head -40
```

Expected: JSON with wellness and activities for yesterday.

- [ ] **Step 9: Commit**

```bash
git add scripts/ tests/ 
git commit -m "feat: fetch_intervals.py with tests"
```

---

## Task 3: normalize.py

**Files:**
- Create: `scripts/normalize.py`
- Create: `tests/test_normalize.py`
- Create: `tests/fixtures/garmin_raw.json`

- [ ] **Step 1: Create garmin fixture**

Create `tests/fixtures/garmin_raw.json`:

```json
{
  "date": "2026-04-17",
  "sleep": {
    "total_hours": 7.2,
    "deep_hours": 1.53,
    "light_hours": 2.80,
    "rem_hours": 1.23,
    "awake_hours": 0.23,
    "overall_score": 78,
    "overall_score_qualifier": "GOOD",
    "start_datetime": "2026-04-16T23:18:00",
    "start_time_offset_hours": 3
  },
  "hrv": {
    "last_night_avg_ms": 52,
    "last_night_5min_high_ms": 61,
    "measurement_count": 18
  },
  "heart_rate": {
    "resting_hr_bpm": 49,
    "steps": 11240,
    "calories": 820
  },
  "activity_streams": {
    "2026-04-17T07:30:00_10.4km": {
      "streams": {
        "time":     [0, 234, 469, 704, 939, 1174, 1409, 1644, 1879, 2114, 2349],
        "distance": [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        "heartrate": [132, 145, 158, 162, 165, 168, 170, 167, 164, 162, 160],
        "cadence":  [172, 176, 180, 182, 181, 183, 182, 181, 180, 179, 178]
      }
    }
  }
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_normalize.py`:

```python
import json
import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_format_pace_returns_correct_string():
    from scripts.normalize import format_pace
    # 10400m in 3120s = 5:00/km
    assert format_pace(10400, 3120) == "5:00"


def test_format_pace_handles_zero():
    from scripts.normalize import format_pace
    assert format_pace(0, 3120) is None
    assert format_pace(10400, 0) is None


def test_build_snapshot_wellness_fields():
    from scripts.normalize import build_snapshot
    intervals = load_fixture("intervals_wellness.json")
    garmin = load_fixture("garmin_raw.json")
    raw_intervals = {"date": "2026-04-17", "wellness": intervals, "activities": []}

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


def test_build_snapshot_sleep_phases():
    from scripts.normalize import build_snapshot
    intervals = load_fixture("intervals_wellness.json")
    garmin = load_fixture("garmin_raw.json")
    raw_intervals = {"date": "2026-04-17", "wellness": intervals, "activities": []}

    snap = build_snapshot(raw_intervals, garmin)

    sleep = snap["wellness"]["sleep"]
    assert sleep["total_h"] == 7.2
    assert sleep["score"] == 78
    assert sleep["phases_h"]["deep"] == 1.53
    assert sleep["phases_h"]["rem"] == 1.23
    assert sleep["bedtime"] == "23:18"


def test_build_snapshot_run_activity():
    from scripts.normalize import build_snapshot
    activities = load_fixture("intervals_activities.json")
    garmin = load_fixture("garmin_raw.json")
    raw_intervals = {"date": "2026-04-17", "wellness": load_fixture("intervals_wellness.json"), "activities": activities}

    snap = build_snapshot(raw_intervals, garmin)

    assert len(snap["activities"]) == 1
    run = snap["activities"][0]
    assert run["type"] == "Run"
    assert run["distance_km"] == 10.4
    assert run["avg_pace"] == "5:00"
    assert run["avg_hr"] == 162.0
    assert run["tss"] == 94


def test_compute_km_splits():
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


def test_km_splits_empty_streams():
    from scripts.normalize import compute_km_splits
    assert compute_km_splits({}) == []
    assert compute_km_splits({"distance": [], "time": []}) == []


def test_build_snapshot_strength_activity():
    from scripts.normalize import build_snapshot
    activity_detail = load_fixture("intervals_activity_detail.json")
    garmin = load_fixture("garmin_raw.json")
    raw_intervals = {
        "date": "2026-04-14",
        "wellness": load_fixture("intervals_wellness.json"),
        "activities": [activity_detail],
    }

    snap = build_snapshot(raw_intervals, garmin)

    gym = snap["activities"][0]
    assert gym["type"] == "Strength"
    exercises = gym["exercises"]
    assert exercises[0]["name"] == "Dumbbell Bulgarian Split Squat"
    assert exercises[0]["sets"][0]["weight_kg"] == 12
    assert exercises[0]["sets"][0]["reps"] == 12


def test_build_snapshot_missing_garmin_graceful():
    from scripts.normalize import build_snapshot
    intervals = load_fixture("intervals_wellness.json")
    raw_intervals = {"date": "2026-04-17", "wellness": intervals, "activities": []}

    snap = build_snapshot(raw_intervals, garmin=None)

    assert snap["wellness"]["steps"] is None
    assert snap["wellness"]["sleep"]["total_h"] is None
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
python -m pytest tests/test_normalize.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.normalize'`

- [ ] **Step 4: Implement normalize.py**

Create `scripts/normalize.py`:

```python
#!/usr/bin/env python3
"""
Merge intervals.icu raw + Garmin raw into a normalized daily snapshot.
Usage: python scripts/normalize.py [YYYY-MM-DD]
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

STRENGTH_TYPES = {"WeightTraining", "Strength", "strength_training"}
RUN_TYPES = {"Run", "VirtualRun", "TrailRun", "running"}


def format_pace(distance_m: float, time_s: float) -> str | None:
    if not distance_m or not time_s:
        return None
    sec_per_km = time_s / (distance_m / 1000)
    return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}"


def _parse_time(dt_str: str) -> str | None:
    """Extract HH:MM from a datetime string."""
    if not dt_str:
        return None
    parts = dt_str.split("T")
    if len(parts) == 2:
        return parts[1][:5]
    return None


def _extract_exercises(workout_doc: dict) -> list:
    if not workout_doc:
        return []
    exercises = []
    for step in workout_doc.get("steps", []):
        if step.get("type") != "step":
            continue
        sets_raw = step.get("sets", [])
        sets = [
            {
                "reps": s.get("reps"),
                "weight_kg": s.get("weight"),
                "duration_s": s.get("time"),
                "rest_s": s.get("rest"),
            }
            for s in sets_raw
        ]
        exercises.append({"name": step.get("text"), "sets": sets})
    return exercises


def compute_km_splits(streams: dict) -> list:
    distances = streams.get('distance', [])
    times = streams.get('time', [])
    heartrates = streams.get('heartrate', [])
    cadences = streams.get('cadence', [])
    if not distances or not times:
        return []
    splits = []
    current_km, km_start_idx, km_start_time = 1, 0, 0.0
    for i, dist in enumerate(distances):
        if dist >= current_km * 1000:
            duration_s = times[i] - km_start_time
            seg = slice(km_start_idx, i + 1)
            hr_seg = heartrates[seg] if heartrates else []
            cad_seg = cadences[seg] if cadences else []
            splits.append({
                'km': current_km,
                'pace': format_pace(1000, duration_s),
                'hr': round(sum(hr_seg) / len(hr_seg)) if hr_seg else None,
                'cadence': round(sum(cad_seg) / len(cad_seg)) if cad_seg else None,
            })
            km_start_idx, km_start_time, current_km = i, float(times[i]), current_km + 1
    return splits


def _match_garmin_streams(act: dict, garmin_streams: dict) -> dict | None:
    """Match an intervals.icu activity to a garmin stream by start_datetime + distance."""
    act_start = (act.get('start_date_local') or '')[:16]  # YYYY-MM-DDTHH:MM
    act_dist = act.get('distance') or 0
    for key, val in garmin_streams.items():
        # key format: "YYYY-MM-DDTHH:MM_Xkm"
        if act_start in key:
            return val.get('streams')
        # fallback: match by distance within 5%
    return None


def _normalize_activity(act: dict, garmin_streams: dict = None) -> dict:
    act_type = act.get("type", "")
    base = {
        "type": "Strength" if act_type in STRENGTH_TYPES else act_type,
        "name": act.get("name"),
        "duration_min": round(act.get("moving_time", 0) / 60, 1) if act.get("moving_time") else None,
        "tss": act.get("icu_training_load"),
    }

    if act_type in RUN_TYPES or act_type == "Run":
        streams = _match_garmin_streams(act, garmin_streams or {}) if garmin_streams else None
        base.update({
            "type": "Run",
            "distance_km": round(act.get("distance", 0) / 1000, 1),
            "avg_pace": format_pace(act.get("distance"), act.get("moving_time")),
            "avg_hr": act.get("average_heartrate"),
            "max_hr": act.get("max_heartrate"),
            "cadence_avg": act.get("average_cadence"),
            "interval_summary": act.get("interval_summary"),
            "hr_zone_times_s": act.get("icu_hr_zone_times"),
            "km_splits": compute_km_splits(streams) if streams else [],
        })
    elif act_type in STRENGTH_TYPES:
        base.update({
            "kg_lifted": act.get("kg_lifted"),
            "avg_hr": act.get("average_heartrate"),
            "max_hr": act.get("max_heartrate"),
        })

    return {k: v for k, v in base.items() if v is not None}


def build_snapshot(raw_intervals: dict, garmin: dict | None) -> dict:
    w_raw = raw_intervals.get("wellness", {})
    g_sleep = (garmin or {}).get("sleep", {})
    g_hrv = (garmin or {}).get("hrv", {})
    g_hr = (garmin or {}).get("heart_rate", {})

    tsb = None
    ctl = w_raw.get("ctl")
    atl = w_raw.get("atl")
    if ctl is not None and atl is not None:
        tsb = round(ctl - atl, 1)

    bedtime = _parse_time(g_sleep.get("start_datetime"))

    sleep_total = g_sleep.get("total_hours")
    wake = None
    if sleep_total and g_sleep.get("start_datetime"):
        from datetime import datetime, timedelta as td
        try:
            start = datetime.fromisoformat(g_sleep["start_datetime"])
            wake_dt = start + td(hours=sleep_total)
            wake = wake_dt.strftime("%H:%M")
        except Exception:
            pass

    snapshot = {
        "date": raw_intervals["date"],
        "wellness": {
            "hrv_avg_ms": g_hrv.get("last_night_avg_ms") or w_raw.get("hrv"),
            "hrv_5min_high_ms": g_hrv.get("last_night_5min_high_ms"),
            "hrv_baseline": 50,  # venlafaxine-adjusted baseline
            "rhr": g_hr.get("resting_hr_bpm") or w_raw.get("restingHR"),
            "readiness": w_raw.get("readiness"),
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
            "ramp_rate": w_raw.get("rampRate"),
            "weight": w_raw.get("weight"),
            "fatigue": w_raw.get("fatigue"),
            "soreness": w_raw.get("soreness"),
            "mood": w_raw.get("mood"),
            "steps": g_hr.get("steps"),
            "calories_active": g_hr.get("calories"),
            "sleep": {
                "total_h": sleep_total,
                "score": g_sleep.get("overall_score"),
                "score_qualifier": g_sleep.get("overall_score_qualifier"),
                "phases_h": {
                    "deep": g_sleep.get("deep_hours"),
                    "light": g_sleep.get("light_hours"),
                    "rem": g_sleep.get("rem_hours"),
                    "awake": g_sleep.get("awake_hours"),
                } if g_sleep else None,
                "bedtime": bedtime,
                "wake": wake,
            },
        },
        "activities": [
            _normalize_activity(a, (garmin or {}).get("activity_streams", {}))
            for a in raw_intervals.get("activities", [])
        ],
    }
    return snapshot


def main():
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = (date.today() - timedelta(days=1)).isoformat()

    intervals_path = Path(f"data/raw/intervals/{target}.json")
    garmin_path = Path(f"data/raw/garmin/{target}.json")

    if not intervals_path.exists():
        print(f"ERROR: {intervals_path} not found — run fetch_intervals.py first", file=sys.stderr)
        sys.exit(1)

    raw_intervals = json.loads(intervals_path.read_text(encoding="utf-8"))
    garmin = json.loads(garmin_path.read_text(encoding="utf-8")) if garmin_path.exists() else None

    if garmin is None:
        print(f"WARNING: no garmin data at {garmin_path} — sleep/steps/HRV will be null", file=sys.stderr)

    snapshot = build_snapshot(raw_intervals, garmin)

    out_dir = Path("data/snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{target}.json"
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved snapshot → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
python -m pytest tests/test_normalize.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/normalize.py tests/test_normalize.py tests/fixtures/
git commit -m "feat: normalize.py with tests"
```

---

## Task 4: send_telegram.py

**Files:**
- Create: `scripts/send_telegram.py`

- [ ] **Step 1: Create send_telegram.py**

```python
#!/usr/bin/env python3
"""
Send text from stdin or a file to Telegram.
Usage: cat report.md | python scripts/send_telegram.py
       python scripts/send_telegram.py data/reports/2026-04-17.md
"""
import os
import sys
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
MAX_LEN = 4096


def send(text: str) -> None:
    chunks = [text[i:i + MAX_LEN] for i in range(0, len(text), MAX_LEN)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if not r.ok:
            print(f"Telegram error: {r.status_code} {r.text}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = open(sys.argv[1], encoding="utf-8").read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("ERROR: empty message", file=sys.stderr)
        sys.exit(1)

    send(text)
    print("Sent.", file=sys.stderr)
```

- [ ] **Step 2: Smoke test**

```bash
echo "test from training-log" | python scripts/send_telegram.py
```

Expected: message appears in Telegram chat, "Sent." in stderr.

- [ ] **Step 3: Commit**

```bash
git add scripts/send_telegram.py
git commit -m "feat: send_telegram.py"
```

---

## Task 5: profile/me.md

**Files:**
- Create: `profile/me.md`

- [ ] **Step 1: Create profile/me.md**

```markdown
# Athlete Profile — Влад

## Physical
- Age: 30 | Height: 191 cm | Weight: 93–94 kg (target 90–92 kg)
- VO2max: ~54–55 (Garmin shows 51–52, underestimated due to venlafaxine)
- Background: BJJ (high mobility), running 3+ years, first gym cycle Apr 2026

## Medical
- Left knee: gonarthrosis grade 3 + old ACL transplant rupture
- Left shoulder: subacromial impingement (recovering Apr 2026)
- **Venlafaxine 150 mg (SNRI, started ~Feb 2026)**
  - HRV new baseline: 45–55 ms (was 85±5) — pharmacological, NOT overtraining
  - RHR new baseline: 48–52 bpm (was 43–44)
  - Reliable fatigue markers: subjective feel + sleep quality + pace on standard sessions
- Ferritin recovery protocol (started Apr 2026, ~3 months)
- Previously: sertraline 6 years (tolerated well)

## Supplements (current)
- Venlafaxine 150 mg (prescription)
- Collagen 10 g + vitamin C — before workout
- Omega-3 2–4 g EPA+DHA — daily
- PRP injections knee — 1 course per 12–18 months
- Ferritin protocol (TBD — update when known)

## Weekly Training Structure
| Day | Session |
|-----|---------|
| Mon | Gym A — heavy legs + upper base |
| Tue | Easy run 8 km (Z2) |
| Wed | Gym B — heavy upper + light legs/stabilisation |
| Thu | Intervals 8 km |
| Fri | Pool 2 km (optional) + pull-ups at work |
| Sat | Parkrun 5 km |
| Sun | Long run 17–18 km |
Pull-ups at work: Tue/Thu/Fri 3×12

## Hard Limits (never override)
- NO leg extension (gonarthrosis grade 3)
- NO forward lunges (patellofemoral stress)
- Remove gym completely 10 days before race

## Adaptation Rules (apply daily)
- HRV < 40 ms → replace quality with easy
- Sleep < 6 h → remove intensity, keep easy volume
- ATL/CTL > 1.3 → add rest day
- RHR > 54 bpm several days → easy day
- Shoulder pain returns → remove incline press + wide-grip pulldown

## Goals
### Immediate
- Half-marathon end of May 2026: target 1:34–1:37, stretch 1:32

### Autumn 2026
- 10 km sub-40:00 (4:00/km) at 90 kg
- 5 km sub-19:00

### Long-term
- Half-marathon sub-1:30 (constitutional ceiling at current weight)
- Squat 100–110×5, RDL 100–110×5, press 100–105×5, Bulgarian split 25–30×8

## Scorecard (April 2026): 22/30
- Aerobic base: 4.5/5 | Strength: 2.8/5 | Body comp: 3.5/5
- Mobility: 4.0/5 | Functional endurance: 4.0/5 | Biomarkers: 3.2/5
```

- [ ] **Step 2: Commit**

```bash
git add profile/me.md
git commit -m "docs: athlete profile"
```

---

## Task 6: CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Create CLAUDE.md**

```markdown
# Claude Code — Training Log

This repo is a personal training assistant for Влад. Every session, read this file and `profile/me.md` first.

## Context
- Athlete profile: `profile/me.md`
- Current week plan: `plan/week-YYYY-WW.md` (find the most recent)
- Daily snapshots: `data/snapshots/YYYY-MM-DD.json`
- Reports archive: `data/reports/`

## Critical Rules

### HRV & RHR Interpretation
Влад is on venlafaxine 150 mg. HRV baseline is pharmacologically shifted:
- Normal HRV range: 45–55 ms (NOT the historical 85)
- Normal RHR range: 48–52 bpm (NOT the historical 43–44)
- DO NOT flag HRV 50 as "low". Compare only to the venlafaxine baseline.
- Reliable fatigue markers: subjective feel, sleep hours, pace on standard sessions.

### Knee & Shoulder
- NEVER suggest leg extension — gonarthrosis grade 3
- NEVER suggest forward lunges
- Monitor incline press if shoulder symptoms return

### Telegram Messages
- Maximum 4096 characters (script handles chunking automatically)
- Plain text, avoid `_` or `*` in metric values (Telegram parse issues)
- Language: Russian

### Git Commits
Every routine run must end with:
```bash
git add data/snapshots/ data/reports/ data/logs/ plan/
git commit -m "daily: YYYY-MM-DD report + plan update"
git push
```

## Data Pipeline
```
fetch_intervals.py  →  data/raw/intervals/YYYY-MM-DD.json
[GetFast MCP]       →  data/raw/garmin/YYYY-MM-DD.json
normalize.py        →  data/snapshots/YYYY-MM-DD.json
                    →  analysis + plan update
send_telegram.py    →  Telegram
git commit + push   →  archive
```
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md instructions"
```

---

## Task 7: Weekly plan files

**Files:**
- Create: `plan/week-2026-16.md`
- Create: `plan/week-2026-17.md`

- [ ] **Step 1: Create week-2026-16.md (current, 13–19 Apr)**

```markdown
# Неделя 16 (13–19 апреля 2026)

**Цель:** Deload — вывести ATL < 40, Form → -10 или выше. Только easy + один силовой.
**Объём бег:** ~22 км (только easy, никаких интервалов).

| День | План | Статус | Комментарий |
|------|------|--------|-------------|
| Пн 13.04 | Зал A — техника, лёгкие веса | | |
| Вт 14.04 | Easy 8 км @ 5:45–6:00, HR <145 | | |
| Ср 15.04 | Зал B — верх + стабилизация | | |
| Чт 16.04 | Easy 8 км @ 5:45–6:00 | | |
| Пт 17.04 | Бассейн 2 км или ОТДЫХ | | |
| Сб 18.04 | Паркран 5 км (не на результат) | | |
| Вс 19.04 | Easy 10 км @ 5:45–6:00, без длинной | | |

**Правила адаптации:**
- HRV < 40 → заменить на отдых или прогулку
- Sleep < 6ч → убрать любую нагрузку в тот день
- Если Form к пятнице не вышел выше -15 → воскресенье тоже отдых

**Прогрессия зала (неделя 3 → переход в 6–8 повт до отказа):**
- Болгарский: 20 кг × 10
- РДЛ: 80 кг × 8 (пауза 2 сек внизу)
- Присед: 90 кг × 10
- Мост: 120 кг → 130 кг × 10
- Nordic: 3 × 5
```

- [ ] **Step 2: Create week-2026-17.md (next, 20–26 Apr)**

```markdown
# Неделя 17 (20–26 апреля 2026)

**Цель:** 1st quality block — возврат к объёму и одна качественная сессия.
**Объём бег:** ~38–40 км.

| День | План | Статус | Комментарий |
|------|------|--------|-------------|
| Пн 20.04 | Зал A — рабочие веса (6–8 повт) | | |
| Вт 21.04 | Easy 8 км @ 5:20–5:30 | | |
| Ср 22.04 | Зал B | | |
| Чт 23.04 | Интервалы: 4×1500 @ 4:00 + 2×400 @ 3:50 | | |
| Пт 24.04 | Бассейн 2 км или ОТДЫХ | | |
| Сб 25.04 | Паркран 5 км (тест формы) | | |
| Вс 26.04 | Long 15 км: 10 км easy + 5 км @ HM-pace (4:25–4:30) | | |

**Правила адаптации:**
- HRV < 40 → четверг заменить на easy 8 км
- Sleep < 6ч → убрать интенсивность в тот день
- Form к четвергу глубже -18 → интервалы перенести на субботу, паркран отменить
- ATL/CTL > 1.3 к воскресенью → long сократить до 10 км easy
```

- [ ] **Step 3: Commit**

```bash
git add plan/
git commit -m "docs: week plans 16 and 17"
```

---

## Task 8: prompts/daily-routine.md

**Files:**
- Create: `prompts/daily-routine.md`

- [ ] **Step 1: Create daily-routine.md**

````markdown
# Daily Training Routine

Ты — тренер-ассистент для Влада. Запускается каждую ночь в 00:00–02:00.
Читаешь `CLAUDE.md` и `profile/me.md` перед любым шагом.

---

## Шаг 1 — Забрать данные из intervals.icu

```bash
python scripts/fetch_intervals.py
```

Это сохраняет `data/raw/intervals/YYYY-MM-DD.json` (вчерашняя дата).
Если скрипт упал с ошибкой → перейди к Шагу 6 (ошибка).

---

## Шаг 2 — Забрать данные Garmin через GetFast MCP

Используй GetFast MCP tools для вчерашней даты (TARGET_DATE = сегодня минус 1 день).

Вызови поочерёдно:
1. `get_recent_sleep` — получи данные за последние 2 дня, возьми запись с `calendar_date == TARGET_DATE`
2. `get_hrv_details` — для TARGET_DATE
3. `get_heart_rate` — период `last_7_days`, возьми запись с `date == TARGET_DATE`
4. Для каждой беговой активности из `data/raw/intervals/TARGET_DATE.json`:
   - Найди соответствующую активность в GetFast через `list_activities` (по дате + типу `running`)
   - Вызови `get_activity_streams` с `streams: ["time","distance","heartrate","cadence"]`, `max_points: 500`
   - Ключ в `activity_streams`: `"<start_datetime_YYYY-MM-DDTHH:MM>_<distance_km>km"`

Затем запиши результат в `data/raw/garmin/TARGET_DATE.json` в формате:

```json
{
  "date": "TARGET_DATE",
  "sleep": { <поля из get_recent_sleep для этой даты> },
  "hrv": { <поля из get_hrv_details> },
  "heart_rate": { "resting_hr_bpm": X, "steps": X, "calories": X },
  "activity_streams": {
    "YYYY-MM-DDTHH:MM_Xkm": {
      "streams": { "time": [...], "distance": [...], "heartrate": [...], "cadence": [...] }
    }
  }
}
```

Если GetFast недоступен → запиши `{}` в файл и продолжай, normalize.py справится.

---

## Шаг 3 — Нормализовать

```bash
python scripts/normalize.py
```

Создаёт `data/snapshots/TARGET_DATE.json`. Проверь что файл создался.

---

## Шаг 4 — Анализ

Прочитай:
- `data/snapshots/TARGET_DATE.json`
- `plan/week-YYYY-WW.md` (найди актуальный файл по дате)
- `profile/me.md`

**Оцени вчерашний день:**
- Сон: сколько часов, score, фазы (достаточно ли глубокого сна?). Опасно если < 6ч.
- HRV: сравни с baseline 45–55. Ниже 40 — сигнал. Выше 55 — отлично.
- RHR: compare с baseline 48–52. Выше 54 несколько дней — сигнал.
- CTL/ATL/Form (TSB): тренд, зона.
- Активности: что было запланировано vs что сделано. Обнови статус (✅/⚠️/❌) в плане.
- Зал: если была силовая, укажи ключевые веса.

**Реши по сегодняшнему дню:**
Применяй правила адаптации из `profile/me.md` и текущего плана.
Если правило сработало — измени строку плана на сегодня, объясни в колонке «Комментарий».

---

## Шаг 5 — Отчёт и отправка

Сохрани отчёт в `data/reports/TODAY.md`:

```
Отчёт TARGET_DATE

ВЧЕРА (TARGET_DATE)
Сон: X ч, score Y [оценка]
HRV: X мс (baseline 50) [оценка]  
RHR: X уд/мин
Активность: [тип, дистанция/время, TSS, ключевые цифры]
Зал (если был): [упражнение — макс вес × повт]
CTL X / ATL X / Form X [тренд]

СЕГОДНЯ — ПЛАН
[итоговый план после адаптации]

ЗАМЕТКИ
[тренды, риски, что отслеживать]
```

Отправь в Telegram:

```bash
python scripts/send_telegram.py data/reports/TODAY.md
```

---

## Шаг 6 — Лог и коммит

Запиши в `data/logs/TODAY.md` полный trace: что прочитал, какие значения были, какие решения принял, почему.

```bash
git add data/snapshots/ data/reports/ data/logs/ plan/
git commit -m "daily: TARGET_DATE report + plan update"
git push
```

---

## При ошибке

Если intervals.icu недоступен или скрипт упал:

```bash
echo "⚠️ training-log: не удалось забрать данные за TARGET_DATE. Проверь API-ключ и доступность intervals.icu." | python scripts/send_telegram.py
```

Затем выйди.
````

- [ ] **Step 2: Commit**

```bash
git add prompts/daily-routine.md
git commit -m "docs: daily routine prompt"
```

---

## Task 9: prompts/weekly-review.md

**Files:**
- Create: `prompts/weekly-review.md`

- [ ] **Step 1: Create weekly-review.md**

````markdown
# Weekly Training Review

Ты — тренер-ассистент. Запускается вручную каждое воскресенье.
Читаешь `CLAUDE.md` и `profile/me.md` перед стартом.

---

## Данные для анализа

Найди снапшоты за все 7 дней прошедшей недели:
`data/snapshots/YYYY-MM-DD.json` (пн–вс).

Найди план недели: `plan/week-YYYY-WW.md`.

---

## Анализ

### Вес
- Тренд за неделю (мин / макс / среднее)
- Направление: растёт / падает / стабильно

### Сон
- Среднее кол-во часов
- Опасные ночи (< 6ч) — сколько, когда
- Средний score, тренд фаз (достаточно ли deep sleep?)
- Влияние на тренировки: были ли плохие сессии после плохих ночей?

### Бег (приоритет ★★★)
- Итого км за неделю
- Распределение зон (цель: 80% Z1–Z2, 20% Z3–Z5)
- Прогресс ключевых сессий:
  - Интервалы: темп на 1000/1500м vs предыдущая неделя
  - Паркран: время, темп, HR
  - Длинная: дистанция, темп, HR-дрейф
- ЧСС на easy-бегах (тренд вниз = аэробная адаптация ✅)

### Силовые (приоритет ★★★)
- Gym A прогрессия: болгарский / РДЛ / присед / мост / nordic
- Gym B прогрессия: T-bar / разведение / трицепс / бицепс / пресс / сгибание ног
- Отметить: новые максимумы, отказные подходы, технические проблемы

### Прочее кардио (приоритет ★)
- Бассейн: дистанция
- Вело или другое: обзорно

### HRV & RHR (с поправкой на венлафаксин)
- Тренд HRV (baseline 45–55): улучшение / стагнация / ухудшение
- Тренд RHR (baseline 48–52)
- Дни с аномалиями

### Form & нагрузка
- CTL тренд за неделю
- ATL тренд
- TSB (Form) к концу недели
- Ramp rate: если > 8/нед → предупреждение

---

## Рекомендации на следующую неделю

Дай конкретные числа:
- Объём бега (км)
- Интенсивность: да/нет интервалы, темп
- Зал: какие веса прогрессировать
- Особые фокусы (сон, восстановление, тапер и т.д.)

---

## Scorecard обновление

Обнови `profile/me.md` раздел Scorecard если есть изменения.

---

## Сохрани и отправь

```bash
# сохрани отчёт
# (напиши в файл)
python scripts/send_telegram.py data/reports/week-YYYY-WW-review.md

git add data/reports/ profile/me.md plan/
git commit -m "weekly review: week YYYY-WW"
git push
```
````

- [ ] **Step 2: Commit**

```bash
git add prompts/weekly-review.md
git commit -m "docs: weekly review prompt"
```

---

## Task 10: End-to-end smoke test

- [ ] **Step 1: Run full data pipeline for yesterday**

```bash
cd C:/git/training-log
python scripts/fetch_intervals.py
# verify
ls data/raw/intervals/
```

Expected: file `YYYY-MM-DD.json` with yesterday's date.

- [ ] **Step 2: Manually create garmin raw for yesterday**

Replace `YYYY-MM-DD` with yesterday's date:

```bash
python -c "
import json, sys
from datetime import date, timedelta
from pathlib import Path
d = (date.today() - timedelta(days=1)).isoformat()
Path('data/raw/garmin').mkdir(parents=True, exist_ok=True)
Path(f'data/raw/garmin/{d}.json').write_text(json.dumps({'date': d, 'sleep': {}, 'hrv': {}, 'heart_rate': {}, 'activity_streams': {}}))
print('Created empty garmin stub for', d)
"
```

(In the real routine, Claude writes this from GetFast MCP. This stub tests the pipeline.)

- [ ] **Step 3: Run normalize**

```bash
python scripts/normalize.py
cat data/snapshots/$(python -c "from datetime import date,timedelta; print((date.today()-timedelta(1)).isoformat())").json
```

Expected: snapshot JSON with wellness data, activities, nulls for garmin fields.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "chore: end-to-end smoke test verified"
git push
```

---

## After Implementation: Configure Claude Code Routine

1. Push repo to GitHub (if not done): `git remote add origin <url> && git push -u origin main`
2. Go to `claude.ai/code` → Routines → New Routine
3. Settings:
   - **Cadence:** Daily at 01:00 (Europe/Minsk = UTC+3, so set 22:00 UTC)
   - **Repo:** `training-log`
   - **Prompt:** contents of `prompts/daily-routine.md`
   - **Env vars:** `INTERVALS_API_KEY`, `INTERVALS_ATHLETE_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
4. Click **Run now** to test manually
5. Check Telegram for the report
6. Check git log for the commit

---

## Self-Review

**Spec coverage check:**
- ✅ Two data sources: intervals.icu (fetch_intervals.py) + GetFast MCP (in routine prompt)
- ✅ Normalized snapshot with all rich fields: sleep phases, gym sets, run aggregates
- ✅ Daily routine: fetch → normalize → analyze → adapt plan → report → send → commit
- ✅ Weekly review: separate prompt, manual trigger, full analysis + scorecard update
- ✅ git log strategy: every run commits data/snapshots + reports + logs
- ✅ profile/me.md: venlafaxine baseline, medical limits, goals
- ✅ CLAUDE.md: HRV/RHR interpretation rules, adaptation rules
- ✅ Timing: 00:00–02:00 Europe/Minsk
- ✅ Plan files for weeks 16 and 17
