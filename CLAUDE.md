# Claude Code — Training Log

This repo is Влад's personal training assistant. Read this file and `profile/me.md` at the start of every session.

## Context
- Athlete profile: `profile/me.md`
- Current week plan: `plan/week-YYYY-WW.md` (use most recent file)
- Daily snapshots: `data/snapshots/YYYY-MM-DD.json`
- Reports archive: `data/reports/`

## Critical Rules

### HRV & RHR Interpretation
Влад is on venlafaxine 150 mg. HRV baseline is pharmacologically shifted:
- Normal HRV: 45–55 ms (NOT historical 85)
- Normal RHR: 48–52 bpm (NOT historical 43–44)
- DO NOT flag HRV 50 as "low". Compare only to venlafaxine baseline.
- Reliable fatigue markers: subjective feel, sleep hours, pace on standard sessions.

### Knee & Shoulder
- NEVER suggest leg extension (gonarthrosis grade 3)
- NEVER suggest forward lunges
- Monitor incline press if shoulder symptoms return

### Telegram Messages
- Maximum 4096 characters (script handles chunking)
- Plain text — avoid `_` or `*` inside metric values
- Language: Russian

### Git Commits
Every routine run must end with:
```bash
git add data/snapshots/ data/reports/ data/logs/ plan/
git commit -m "daily: YYYY-MM-DD report + plan update"
git push
```

## Ручной трекинг прогресса

### Зал — data/gym/log.md
После каждой тренировки добавляй строку в нужную таблицу.
Формат веса: одно значение если все подходы одинаковые, через / если рос (80/90/100).
Флаги: ⚠️ колено, ⚠️ плечо — записывай в раздел "Флаги и наблюдения".

### Бег — data/running/log.md
После каждой пробежки добавляй в нужный раздел (лонг / интервалы / паркран / easy).
Z1+Z2% = (zone1_s + zone2_s) / total_s * 100 — из снапшота hr_zone_times_s.
Недельный объём обновляй в воскресенье вручную или по данным отчёта.
Цель: Z1+Z2% ≥ 80 по итогу недели.

## Data Pipeline
```
fetch_intervals.py        →  data/raw/intervals/YYYY-MM-DD.json
[Claude: GetFast MCP]     →  data/raw/garmin/YYYY-MM-DD.json
normalize.py              →  data/snapshots/YYYY-MM-DD.json
[Claude: analyze + write] →  data/reports/ + data/logs/ + plan/
send_telegram.py          →  Telegram
git commit + push         →  archive
```
