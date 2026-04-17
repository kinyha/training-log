#!/usr/bin/env python3
"""
Merge intervals.icu raw + Garmin raw into a normalized daily snapshot.
Usage: python scripts/normalize.py [YYYY-MM-DD]
"""
import json
import os
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

STRENGTH_TYPES = {"WeightTraining", "Strength", "strength_training"}
RUN_TYPES = {"Run", "VirtualRun", "TrailRun", "running"}


def format_pace(distance_m, time_s):
    if not distance_m or not time_s:
        return None
    sec_per_km = time_s / (distance_m / 1000)
    return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}"


def compute_km_splits(streams: dict) -> list:
    distances = streams.get("distance", [])
    times = streams.get("time", [])
    heartrates = streams.get("heartrate", [])
    cadences = streams.get("cadence", [])
    if not distances or not times:
        return []
    splits = []
    current_km = 1
    km_start_idx = 0
    km_start_time = 0.0
    for i, dist in enumerate(distances):
        if dist >= current_km * 1000:
            duration_s = times[i] - km_start_time
            seg = slice(km_start_idx, i + 1)
            hr_seg = heartrates[seg] if heartrates else []
            cad_seg = cadences[seg] if cadences else []
            splits.append({
                "km": current_km,
                "pace": format_pace(1000, duration_s),
                "hr": round(sum(hr_seg) / len(hr_seg)) if hr_seg else None,
                "cadence": round(sum(cad_seg) / len(cad_seg)) if cad_seg else None,
            })
            km_start_idx = i
            km_start_time = float(times[i])
            current_km += 1
    return splits


def _parse_time(dt_str: str):
    if not dt_str:
        return None
    parts = dt_str.split("T")
    if len(parts) == 2:
        return parts[1][:5]
    return None


def _match_garmin_streams(act: dict, activity_streams: dict):
    """Match activity to garmin streams by start_datetime prefix."""
    act_start = (act.get("start_date_local") or "")[:16].replace("T", "T")  # YYYY-MM-DDTHH:MM
    for key, val in activity_streams.items():
        if act_start in key:
            return val.get("streams")
    return None


def _normalize_activity(act: dict, activity_streams: dict = None) -> dict:
    act_type = act.get("type", "")
    base = {
        "name": act.get("name"),
        "duration_min": round(act.get("moving_time", 0) / 60, 1) if act.get("moving_time") else None,
        "tss": act.get("icu_training_load"),
    }

    if act_type in RUN_TYPES or act_type == "Run":
        streams = _match_garmin_streams(act, activity_streams or {})
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
            "type": "Strength",
            "kg_lifted": act.get("kg_lifted"),
            "avg_hr": act.get("average_heartrate"),
            "max_hr": act.get("max_heartrate"),
            "description": act.get("description") or None,
        })
    else:
        base["type"] = act_type

    return {k: v for k, v in base.items() if v is not None}


def build_snapshot(raw_intervals: dict, garmin) -> dict:
    w = raw_intervals.get("wellness", {})
    g_sleep = (garmin or {}).get("sleep", {})
    g_hrv = (garmin or {}).get("hrv", {})
    g_hr = (garmin or {}).get("heart_rate", {})
    g_streams = (garmin or {}).get("activity_streams", {})

    ctl = w.get("ctl")
    atl = w.get("atl")
    tsb = round(ctl - atl, 1) if ctl is not None and atl is not None else None

    bedtime = _parse_time(g_sleep.get("start_datetime"))
    wake = None
    if g_sleep.get("total_hours") and g_sleep.get("start_datetime"):
        try:
            start = datetime.fromisoformat(g_sleep["start_datetime"])
            from datetime import timedelta as td
            wake_dt = start + td(hours=g_sleep["total_hours"])
            wake = wake_dt.strftime("%H:%M")
        except Exception:
            pass

    return {
        "date": raw_intervals["date"],
        "wellness": {
            "hrv_avg_ms": g_hrv.get("last_night_avg_ms") or w.get("hrv"),
            "hrv_5min_high_ms": g_hrv.get("last_night_5min_high_ms"),
            "hrv_baseline": 50,
            "rhr": g_hr.get("resting_hr_bpm") or w.get("restingHR"),
            "readiness": w.get("readiness"),
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
            "ramp_rate": w.get("rampRate"),
            "weight": w.get("weight"),
            "fatigue": w.get("fatigue"),
            "soreness": w.get("soreness"),
            "mood": w.get("mood"),
            "steps": g_hr.get("steps"),
            "calories_active": g_hr.get("calories"),
            "sleep": {
                "total_h": g_sleep.get("total_hours"),
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
            _normalize_activity(a, g_streams)
            for a in raw_intervals.get("activities", [])
        ],
    }


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=1)).isoformat()

    intervals_path = Path(f"data/raw/intervals/{target}.json")
    garmin_path = Path(f"data/raw/garmin/{target}.json")

    if not intervals_path.exists():
        print(f"ERROR: {intervals_path} not found", file=sys.stderr)
        sys.exit(1)

    raw_intervals = json.loads(intervals_path.read_text(encoding="utf-8"))
    garmin = json.loads(garmin_path.read_text(encoding="utf-8")) if garmin_path.exists() else None

    if garmin is None:
        print(f"WARNING: no garmin data at {garmin_path} — sleep/steps/HRV will be null", file=sys.stderr)

    snapshot = build_snapshot(raw_intervals, garmin)

    out_path = Path(f"data/snapshots/{target}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved snapshot → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
