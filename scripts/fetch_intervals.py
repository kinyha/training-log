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


def _get(url: str, api_key: str, params: dict = None):
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
            try:
                detail = fetch_activity_detail(act_id, api_key)
                activities_detailed.append(detail)
            except Exception as e:
                print(f"WARNING: could not fetch detail for {act_id}: {e}", file=sys.stderr)
                activities_detailed.append(act)
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
