#!/usr/bin/env python3
"""
Оркестратор ручного catchup для training-log.

Подкоманды:
  sync-range --from YYYY-MM-DD [--to YYYY-MM-DD] [--force]
      Для каждой даты в диапазоне: fetch_intervals (если нет raw) + normalize.
      MCP-вызовы к Garmin делает Claude в slash-команде — pipeline.py их не трогает.

  build-week-summary --week YYYY-WW [--through YYYY-MM-DD]
      Читает снапшоты недели и печатает JSON со сводкой (km бег, сессии зала,
      kg_lifted, CTL/ATL/TSB, средние сон/HRV/RHR, тренд веса).

  digest --week YYYY-WW --mode {sync,weekly} [--since YYYY-MM-DD]
      Собирает текст TG-дайджеста на stdout. Режим sync — короткий ежедневный;
      weekly — итог недели + план следующей.

Использование из slash-команды:
  python scripts/pipeline.py sync-range --from 2026-04-20
  python scripts/pipeline.py build-week-summary --week 2026-17
  python scripts/pipeline.py digest --week 2026-17 --mode sync --since 2026-04-20
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = REPO_ROOT / "data" / "snapshots"
RAW_INTERVALS_DIR = REPO_ROOT / "data" / "raw" / "intervals"


def iso_week_monday(year: int, week: int) -> date:
    """Monday of given ISO year/week."""
    return date.fromisocalendar(year, week, 1)


def parse_week(week: str) -> tuple[int, int]:
    """'2026-17' or '2026-W17' → (2026, 17)."""
    s = week.replace("W", "").replace("w", "")
    parts = s.split("-")
    return int(parts[0]), int(parts[1])


def week_dates(year: int, week: int) -> list[date]:
    mon = iso_week_monday(year, week)
    return [mon + timedelta(days=i) for i in range(7)]


def load_snapshot(d: date) -> dict | None:
    path = SNAPSHOTS_DIR / f"{d.isoformat()}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── sync-range ────────────────────────────────────────────────────────────

def cmd_sync_range(args: argparse.Namespace) -> int:
    from fetch_intervals import (
        fetch_wellness, fetch_activities, fetch_activity_detail,
    )
    from normalize import build_snapshot
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    athlete_id = os.environ["INTERVALS_ATHLETE_ID"]
    api_key = os.environ["INTERVALS_API_KEY"]

    start = date.fromisoformat(args.from_)
    end = date.fromisoformat(args.to) if args.to else date.today()
    if end < start:
        print(f"ERROR: --to {end} before --from {start}", file=sys.stderr)
        return 1

    day = start
    processed: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []

    while day <= end:
        d_iso = day.isoformat()
        raw_path = RAW_INTERVALS_DIR / f"{d_iso}.json"
        snap_path = SNAPSHOTS_DIR / f"{d_iso}.json"

        if snap_path.exists() and not args.force:
            skipped.append(d_iso)
            day += timedelta(days=1)
            continue

        try:
            if not raw_path.exists() or args.force:
                wellness = fetch_wellness(athlete_id, api_key, d_iso)
                activities = fetch_activities(athlete_id, api_key, d_iso)
                detailed = []
                for act in activities:
                    act_id = act.get("id")
                    if act_id:
                        try:
                            detailed.append(fetch_activity_detail(act_id, api_key))
                        except Exception as e:
                            print(f"WARN: detail for {act_id}: {e}", file=sys.stderr)
                            detailed.append(act)
                    else:
                        detailed.append(act)
                raw = {"date": d_iso, "wellness": wellness, "activities": detailed}
                RAW_INTERVALS_DIR.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(
                    json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            garmin_path = REPO_ROOT / "data" / "raw" / "garmin" / f"{d_iso}.json"
            garmin = (
                json.loads(garmin_path.read_text(encoding="utf-8"))
                if garmin_path.exists() else None
            )
            snapshot = build_snapshot(raw, garmin)
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            processed.append(d_iso)
        except Exception as e:
            failed.append((d_iso, str(e)))

        day += timedelta(days=1)

    result = {
        "processed": processed,
        "skipped": skipped,
        "failed": [{"date": d, "error": e} for d, e in failed],
        "from": start.isoformat(),
        "to": end.isoformat(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


# ── build-week-summary ────────────────────────────────────────────────────

def cmd_build_week_summary(args: argparse.Namespace) -> int:
    year, week = parse_week(args.week)
    dates = week_dates(year, week)
    through = date.fromisoformat(args.through) if args.through else date.today()

    snaps: list[tuple[date, dict]] = []
    for d in dates:
        if d > through:
            break
        snap = load_snapshot(d)
        if snap:
            snaps.append((d, snap))

    if not snaps:
        print(json.dumps({"week": args.week, "empty": True}, ensure_ascii=False, indent=2))
        return 0

    run_km = 0.0
    run_sessions = 0
    gym_sessions = 0
    kg_lifted = 0.0
    hr_zone_totals = [0, 0, 0, 0, 0]

    for _, s in snaps:
        for act in s.get("activities", []):
            t = act.get("type")
            if t == "Run":
                run_km += act.get("distance_km") or 0
                run_sessions += 1
                zones = act.get("hr_zone_times_s") or []
                for i, z in enumerate(zones[:5]):
                    hr_zone_totals[i] += z or 0
            elif t == "Strength":
                gym_sessions += 1
                kg_lifted += act.get("kg_lifted") or 0

    last = snaps[-1][1].get("wellness", {})

    def _avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    sleep_vals = [s.get("wellness", {}).get("sleep", {}).get("total_h") for _, s in snaps]
    hrv_vals = [s.get("wellness", {}).get("hrv_avg_ms") for _, s in snaps]
    rhr_vals = [s.get("wellness", {}).get("rhr") for _, s in snaps]
    weight_vals = [s.get("wellness", {}).get("weight") for _, s in snaps if s.get("wellness", {}).get("weight")]

    total_zones_s = sum(hr_zone_totals)
    z12_pct = round((hr_zone_totals[0] + hr_zone_totals[1]) / total_zones_s * 100) if total_zones_s else None

    result = {
        "week": args.week,
        "range": {"from": dates[0].isoformat(), "to": dates[-1].isoformat()},
        "days_with_data": len(snaps),
        "through": through.isoformat(),
        "run": {
            "km": round(run_km, 1),
            "sessions": run_sessions,
            "z1_z2_pct": z12_pct,
        },
        "gym": {
            "sessions": gym_sessions,
            "kg_lifted": int(kg_lifted),
        },
        "form": {
            "ctl": last.get("ctl"),
            "atl": last.get("atl"),
            "tsb": last.get("tsb"),
        },
        "sleep_avg_h": _avg(sleep_vals),
        "hrv_avg_ms": _avg(hrv_vals),
        "rhr_avg_bpm": _avg(rhr_vals),
        "weight": {
            "min": min(weight_vals) if weight_vals else None,
            "max": max(weight_vals) if weight_vals else None,
            "avg": _avg(weight_vals),
            "trend_kg": round(weight_vals[-1] - weight_vals[0], 1) if len(weight_vals) >= 2 else None,
        },
        "last_updated": snaps[-1][0].isoformat(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


# ── digest ────────────────────────────────────────────────────────────────

def _interpret_tsb(tsb: float | None) -> str:
    if tsb is None:
        return ""
    if tsb < -20:
        return "высокая усталость"
    if tsb < -10:
        return "усталость"
    if tsb < 5:
        return "норма"
    if tsb < 15:
        return "свежесть"
    return "пик свежести"


def cmd_digest(args: argparse.Namespace) -> int:
    # Reuse summary logic to get metrics
    summary_args = argparse.Namespace(week=args.week, through=None)
    year, week = parse_week(args.week)
    dates = week_dates(year, week)

    snaps: list[tuple[date, dict]] = []
    for d in dates:
        snap = load_snapshot(d)
        if snap:
            snaps.append((d, snap))

    if not snaps:
        print(f"Нет данных для недели {args.week}.")
        return 0

    # reuse the build_week_summary logic inline for brevity
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_build_week_summary(summary_args)
    summary = json.loads(buf.getvalue())

    lines: list[str] = []
    if args.mode == "sync":
        since = args.since or snaps[0][0].isoformat()
        since_date = date.fromisoformat(since)
        n_days = sum(1 for d, _ in snaps if d >= since_date)
        lines.append(f"Sync {date.today().isoformat()} (+{n_days} дней)")
        lines.append("")
        lines.append(f"НЕДЕЛЯ {week} ({dates[0].strftime('%d.%m')}–{dates[-1].strftime('%d.%m')})")
        lines.append(
            f"Бег: {summary['run']['km']} км ({summary['run']['sessions']} сесс)"
            + (f", Z1+Z2 {summary['run']['z1_z2_pct']}%" if summary['run']['z1_z2_pct'] is not None else "")
        )
        lines.append(
            f"Зал: {summary['gym']['sessions']} сесс, kg_lifted {summary['gym']['kg_lifted']}"
        )
        lines.append("")
        lines.append(f"ФАКТ ЗА {n_days} ДНЕЙ")
        for d, s in snaps:
            if d < since_date:
                continue
            acts = s.get("activities") or []
            act_summary = ", ".join(_short_act(a) for a in acts) if acts else "rest"
            lines.append(f"{d.strftime('%a %d.%m')}: {act_summary}")
        lines.append("")
        form = summary["form"]
        lines.append("ТЕЛО")
        lines.append(f"Сон ср: {summary['sleep_avg_h']}ч | HRV: {summary['hrv_avg_ms']} мс | RHR: {summary['rhr_avg_bpm']} bpm")
        if summary["weight"]["avg"]:
            trend = summary["weight"]["trend_kg"]
            trend_s = f" (тренд {trend:+.1f})" if trend is not None else ""
            lines.append(f"Вес: {summary['weight']['avg']} кг{trend_s}")
        lines.append(
            f"CTL {form['ctl']:.0f} / ATL {form['atl']:.0f} / TSB {form['tsb']:+.0f} ({_interpret_tsb(form['tsb'])})"
        )
    elif args.mode == "weekly":
        lines.append(f"Итог недели {week} + план недели {week + 1}")
        lines.append("")
        lines.append(f"НЕДЕЛЯ {week}")
        run_status = "✅" if summary["run"]["sessions"] >= 3 else "⚠️"
        lines.append(
            f"Бег: {summary['run']['km']} км {run_status}"
            + (f" | Z1+Z2 {summary['run']['z1_z2_pct']}%" if summary['run']['z1_z2_pct'] is not None else "")
        )
        lines.append(
            f"Зал: {summary['gym']['sessions']} сесс | kg_lifted {summary['gym']['kg_lifted']}"
        )
        lines.append(f"Сон ср: {summary['sleep_avg_h']}ч | HRV ср: {summary['hrv_avg_ms']} | RHR ср: {summary['rhr_avg_bpm']}")
        form = summary["form"]
        lines.append(f"CTL {form['ctl']:.0f} / ATL {form['atl']:.0f} / TSB {form['tsb']:+.0f}")
        w = summary["weight"]
        if w["min"] and w["max"]:
            lines.append(f"Вес тренд: {w['min']:.1f}→{w['max']:.1f} (ср {w['avg']:.1f} кг)")
        lines.append("")
        lines.append("Review и черновик следующей недели — в weeks/.")
    else:
        print(f"ERROR: unknown mode {args.mode}", file=sys.stderr)
        return 1

    print("\n".join(lines))
    return 0


def _short_act(act: dict) -> str:
    t = act.get("type")
    if t == "Run":
        km = act.get("distance_km")
        pace = act.get("avg_pace")
        hr = act.get("avg_hr")
        return f"Бег {km}км @ {pace}, HR {hr}"
    if t == "Strength":
        dur = act.get("duration_min")
        kg = act.get("kg_lifted") or 0
        return f"Зал {int(dur)}мин, kg {int(kg)}"
    return f"{t} {int(act.get('duration_min', 0))}мин"


# ── main ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Training-log pipeline orchestrator.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync-range", help="Fetch + normalize for date range.")
    p_sync.add_argument("--from", dest="from_", required=True, help="YYYY-MM-DD")
    p_sync.add_argument("--to", dest="to", default=None, help="YYYY-MM-DD (default: today)")
    p_sync.add_argument("--force", action="store_true", help="Re-fetch even if snapshot exists")
    p_sync.set_defaults(fn=cmd_sync_range)

    p_sum = sub.add_parser("build-week-summary", help="Compute week metrics from snapshots.")
    p_sum.add_argument("--week", required=True, help="YYYY-WW or YYYY-W17")
    p_sum.add_argument("--through", default=None, help="Last date to include (default: today)")
    p_sum.set_defaults(fn=cmd_build_week_summary)

    p_dig = sub.add_parser("digest", help="Build TG digest text.")
    p_dig.add_argument("--week", required=True)
    p_dig.add_argument("--mode", choices=["sync", "weekly"], required=True)
    p_dig.add_argument("--since", default=None, help="YYYY-MM-DD (for sync mode)")
    p_dig.set_defaults(fn=cmd_digest)

    args = parser.parse_args()
    # Make scripts importable
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
