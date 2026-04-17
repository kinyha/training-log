#!/usr/bin/env python3
"""
intervals.icu data fetcher — для Vlad (i464516)

Вытягивает:
  - Activities за период (TSS, темп, HR, pace zones)
  - Wellness за период (CTL/ATL/Form + HRV/RHR/sleep)
  - Athlete info

Запуск:
    pip install requests
    python intervals_fetch.py

ВАЖНО: после запуска смени API key в Settings → Developer Settings.
"""

import json
import base64
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

API_KEY = os.environ["INTERVALS_API_KEY"]
ATHLETE_ID = os.environ["INTERVALS_ATHLETE_ID"]
DAYS_BACK = 42  # 6 недель — покроет всю текущую подготовку к HM
OUTPUT_DIR = Path("intervals_data")

BASE_URL = "https://intervals.icu/api/v1"


def get_auth_header(api_key: str) -> dict:
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def fetch(endpoint: str, headers: dict, params: dict = None):
    url = f"{BASE_URL}{endpoint}"
    print(f"  GET {endpoint}", file=sys.stderr)
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 401:
        print("❌ 401 — неверный API key", file=sys.stderr)
        sys.exit(1)
    if r.status_code == 403:
        print("❌ 403 — неверный athlete_id", file=sys.stderr)
        sys.exit(1)
    r.raise_for_status()
    return r.json()


def fmt_pace(time_s: float, dist_m: float) -> str:
    if not dist_m or not time_s:
        return "-"
    sec_per_km = time_s / (dist_m / 1000)
    return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}"


def summarize_activities(activities: list) -> None:
    runs = [a for a in activities if a.get("type") in ("Run", "VirtualRun", "TrailRun")]
    print(f"\n=== ACTIVITIES ({len(activities)} total, {len(runs)} runs) ===")

    if not runs:
        return

    total_km = sum((a.get("distance") or 0) for a in runs) / 1000
    total_time = sum((a.get("moving_time") or 0) for a in runs) / 3600
    total_tss = sum((a.get("icu_training_load") or 0) for a in runs)

    print(f"Total distance: {total_km:.1f} km")
    print(f"Total time: {total_time:.1f} h")
    print(f"Total TSS: {total_tss:.0f}")
    print(f"Avg TSS/run: {total_tss / len(runs):.0f}")

    # Weekly breakdown
    from collections import defaultdict
    weekly = defaultdict(lambda: {"km": 0, "tss": 0, "runs": 0})
    for a in runs:
        date_str = (a.get("start_date_local") or "")[:10]
        if not date_str:
            continue
        d = datetime.fromisoformat(date_str).date()
        monday = d - timedelta(days=d.weekday())
        weekly[monday]["km"] += (a.get("distance") or 0) / 1000
        weekly[monday]["tss"] += a.get("icu_training_load") or 0
        weekly[monday]["runs"] += 1

    print("\nWeekly breakdown:")
    print(f"{'Week start':<12} {'Runs':>5} {'km':>6} {'TSS':>6}")
    for monday in sorted(weekly.keys()):
        w = weekly[monday]
        print(f"{monday.isoformat():<12} {w['runs']:>5} {w['km']:>6.1f} {w['tss']:>6.0f}")

    print("\nLast 15 runs:")
    print(f"{'Date':<12} {'Name':<30} {'km':>6} {'pace':>7} {'HR':>4} {'maxHR':>5} {'TSS':>5}")
    for a in runs[:15]:
        date = (a.get("start_date_local") or "")[:10]
        name = (a.get("name") or "")[:28]
        dist = a.get("distance") or 0
        time_s = a.get("moving_time") or 0
        pace = fmt_pace(time_s, dist)
        hr = a.get("average_heartrate") or 0
        maxhr = a.get("max_heartrate") or 0
        tss = a.get("icu_training_load") or 0
        print(f"{date:<12} {name:<30} {dist/1000:>6.1f} {pace:>7} {hr:>4.0f} {maxhr:>5.0f} {tss:>5.0f}")


def summarize_wellness(wellness: list) -> None:
    print(f"\n=== WELLNESS ({len(wellness)} days) ===")
    w_sorted = sorted(wellness, key=lambda x: x.get("id", ""))

    print(f"{'Date':<12} {'CTL':>5} {'ATL':>5} {'Form':>6} {'HRV':>5} {'RHR':>4} {'Sleep':>6} {'Wt':>5}")
    for w in w_sorted[-21:]:  # последние 3 недели
        date = w.get("id", "")
        ctl = w.get("ctl") or 0
        atl = w.get("atl") or 0
        form = ctl - atl
        hrv = w.get("hrv") or 0
        rhr = w.get("restingHR") or 0
        sleep_h = (w.get("sleepSecs") or 0) / 3600
        weight = w.get("weight") or 0
        print(f"{date:<12} {ctl:>5.1f} {atl:>5.1f} {form:>+6.1f} {hrv:>5.0f} {rhr:>4.0f} {sleep_h:>6.2f} {weight:>5.1f}")

    if w_sorted:
        latest = w_sorted[-1]
        ctl = latest.get("ctl") or 0
        atl = latest.get("atl") or 0
        ramp = latest.get("rampRate") or 0
        form = ctl - atl

        print(f"\n=== CURRENT STATE ({latest.get('id')}) ===")
        print(f"  Fitness (CTL):  {ctl:.1f}")
        print(f"  Fatigue (ATL):  {atl:.1f}")
        print(f"  Form (TSB):     {form:+.1f}")
        print(f"  Ramp rate:      {ramp:+.1f} /week")

        if form < -20:
            print("  ⚠️  Deep negative form — high fatigue, не время для гонок")
        elif form < -10:
            print("  🟡 Productive training — fatigue есть, но контролируемый")
        elif form < -5:
            print("  🟢 Optimal training zone")
        elif form <= 5:
            print("  🟢 Neutral — свежий, готов к качеству или гонке")
        else:
            print("  🔵 Positive form — отдохнувший (risk detraining если долго)")

        if ramp > 8:
            print("  ⚠️  Ramp rate >8 — высокий risk травмы (Gabbett 2016)")
        elif ramp > 5:
            print("  🟡 Aggressive ramp — следи за сигналами")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    headers = get_auth_header(API_KEY)

    today = datetime.now().date()
    oldest = (today - timedelta(days=DAYS_BACK)).isoformat()
    newest = today.isoformat()
    print(f"Period: {oldest} → {newest}", file=sys.stderr)

    print("\nFetching athlete...", file=sys.stderr)
    athlete = fetch(f"/athlete/{ATHLETE_ID}", headers)
    (OUTPUT_DIR / "athlete.json").write_text(
        json.dumps(athlete, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("Fetching activities...", file=sys.stderr)
    activities = fetch(
        f"/athlete/{ATHLETE_ID}/activities",
        headers,
        params={"oldest": oldest, "newest": newest},
    )
    (OUTPUT_DIR / "activities.json").write_text(
        json.dumps(activities, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("Fetching wellness...", file=sys.stderr)
    wellness = fetch(
        f"/athlete/{ATHLETE_ID}/wellness",
        headers,
        params={"oldest": oldest, "newest": newest},
    )
    (OUTPUT_DIR / "wellness.json").write_text(
        json.dumps(wellness, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n✅ Saved to ./{OUTPUT_DIR}/", file=sys.stderr)

    print(f"\n=== ATHLETE ===")
    print(f"Name: {athlete.get('name')}")
    print(f"Weight: {athlete.get('weight')} kg")
    sport_settings = athlete.get("sportSettings") or []
    for s in sport_settings:
        if s.get("types") and "Run" in s.get("types", []):
            print(f"Run FTHR: {s.get('lthr')}, Max HR: {s.get('max_hr')}")
            print(f"Threshold pace: {s.get('threshold_pace')} m/s")
            break

    summarize_activities(activities)
    summarize_wellness(wellness)


if __name__ == "__main__":
    main()
