# Design: Daily Training Routine System

**Date:** 2026-04-17  
**Status:** Approved

---

## Overview

Автоматизированная система ежедневного анализа тренировок и планирования для Влада. Работает на Claude Code Routines (инфраструктура Anthropic, без VPS). Запускается ночью (00:00–02:00), к утру в Telegram уже лежит итог уходящего дня и план на наступающий.

---

## Architecture

```
Claude Code Routine (00:00–02:00 Europe/Minsk)
    │
    ├── fetch_intervals.py   ← wellness + activity list + детали (зал: сеты/веса)
    ├── fetch_garmin.py      ← сон с фазами, шаги, калории, HRV, беговые стримы
    │
    ├── normalize.py         ← объединяет в data/snapshots/YYYY-MM-DD.json
    │
    ├── Читает:
    │   ├── data/snapshots/YYYY-MM-DD.json   ← единый богатый снапшот дня
    │   ├── plan/week-YYYY-WW.md
    │   └── profile/me.md
    │
    ├── Анализирует + адаптирует план на завтра
    │
    ├── Пишет:
    │   ├── data/reports/YYYY-MM-DD.md        ← Telegram-сообщение (≤2000 символов)
    │   └── data/logs/YYYY-MM-DD.md           ← полный trace + решения
    │
    ├── send_telegram.py
    └── git commit + push  ← git история = полный архив
```

---

## Repository Structure

```
training-log/
├── CLAUDE.md
├── profile/
│   └── me.md                        # медицина, добавки, цели, ограничения
├── prompts/
│   ├── daily-routine.md             # ежедневный промпт (Routine, авто)
│   └── weekly-review.md             # еженедельный ревью (ручной запуск)
├── scripts/
│   ├── fetch_intervals.py           # intervals.icu: wellness + activities + зал
│   ├── fetch_garmin.py              # GetFast MCP: сон, HRV, шаги, стримы
│   ├── normalize.py                 # объединяет в единый snapshot
│   └── send_telegram.py
├── plan/
│   ├── week-YYYY-WW.md
│   └── archive/
├── data/
│   ├── snapshots/YYYY-MM-DD.json   ← главный файл дня (богатый, структурированный)
│   ├── reports/YYYY-MM-DD.md       ← Telegram-архив
│   └── logs/YYYY-MM-DD.md          ← полный trace routine
├── requirements.txt
├── .env / .env.example / .gitignore
```

---

## Data Sources

| Данные | Источник | Endpoint / Tool |
|--------|----------|-----------------|
| CTL / ATL / TSB / TSS | intervals.icu | `/wellness/{date}` |
| HR-зоны (разбивка по зонам) | intervals.icu | `/activities` |
| **Зал: упражнения, сеты, веса** | intervals.icu | `/activities/{id}` detail |
| Вес, настроение, болезненность | intervals.icu | `/wellness/{date}` |
| Сон — фазы (REM/deep/light/awake) | GetFast (Garmin) | `get_recent_sleep` |
| Шаги / активные калории | GetFast (Garmin) | `get_heart_rate` |
| HRV детально (avg + 5min high) | GetFast (Garmin) | `get_hrv_details` |
| Беговые сплиты (HR/темп/каденс/км) | GetFast (Garmin) | `get_activity_streams` |

---

## Snapshot Format (`data/snapshots/YYYY-MM-DD.json`)

```json
{
  "date": "2026-04-17",
  "wellness": {
    "hrv_avg_ms": 52, "hrv_5min_high_ms": 61, "hrv_baseline": 50,
    "rhr": 49,
    "readiness": 75, "ctl": 31.2, "atl": 47.1, "tsb": -15.9,
    "weight": 93.0, "fatigue": 2, "soreness": 2, "mood": 3,
    "steps": 11240, "calories_active": 820,
    "sleep": {
      "total_h": 7.2, "score": 78, "score_qualifier": "good",
      "phases_h": {"deep": 1.53, "light": 2.80, "rem": 1.23, "awake": 0.23},
      "bedtime": "23:18", "wake": "06:30"
    }
  },
  "activities": [
    {
      "type": "Run",
      "name": "Threshold intervals",
      "distance_km": 10.4, "duration_min": 52,
      "avg_pace": "5:00", "avg_hr": 162, "max_hr": 179,
      "tss": 94, "cadence_avg": 178,
      "zones_min": {"z1": 4, "z2": 8, "z3": 6, "z4": 18, "z5": 12},
      "km_splits": [
        {"km": 1, "pace": "5:45", "hr": 142, "cadence": 172, "elevation_m": 3},
        {"km": 2, "pace": "4:02", "hr": 168, "cadence": 182, "elevation_m": -1}
      ]
    },
    {
      "type": "Strength",
      "name": "Gym A",
      "duration_min": 58, "tss": 45,
      "exercises": [
        {
          "name": "Dumbbell Bulgarian Split Squat",
          "sets": [
            {"set": 1, "reps": 12, "weight_kg": 12, "duration_s": 74, "rest_s": 157},
            {"set": 2, "reps": 12, "weight_kg": 12, "duration_s": 80, "rest_s": 169}
          ]
        },
        {
          "name": "Romanian Deadlift",
          "sets": [
            {"set": 1, "reps": 14, "weight_kg": 60},
            {"set": 2, "reps": 12, "weight_kg": 80},
            {"set": 3, "reps": 12, "weight_kg": 80}
          ]
        }
      ]
    }
  ]
}
```

---

## Two Routines

### Daily (автоматически, 00:00–02:00 Europe/Minsk)

1. `python scripts/fetch_intervals.py` → wellness + activities + gym details
2. `python scripts/fetch_garmin.py` → сон фазы + HRV + шаги + стримы
3. `python scripts/normalize.py` → `data/snapshots/<дата>.json`
4. Читает snapshot + `plan/week-*.md` + `profile/me.md`
5. Обновляет статус дня в плане (✅/⚠️/❌)
6. Применяет адаптационные правила для завтра
7. Пишет `data/reports/<дата>.md` (≤2000 символов)
8. Пишет `data/logs/<дата>.md` (полный trace)
9. Отправляет в Telegram
10. `git commit -m "daily: <дата>" && git push`

### Weekly Review (вручную, воскресенье)

Читает 7 снапшотов + plan недели. Анализирует:
- Вес: тренд
- Сон: среднее, опасные ночи (<6ч), фазы-тренд
- Бег: объём км, распределение зон (цель 80/20), темп-прогресс на стандартных сессиях
- Силовые: прогрессия весов по упражнениям (Gym A и B)
- Прочее кардио: обзорно
- HRV/RHR с поправкой на венлафаксин (baseline 45-55 / 48-52)
- Scorecard update + рекомендации с конкретными числами
- Сохраняет `data/reports/week-YYYY-WW-review.md` + отправляет в Telegram

---

## CLAUDE.md Rules

- HRV/RHR читать относительно baseline на венлафаксине (45-55 / 48-52), не исторических
- Надёжные маркеры усталости: ощущения + сон + темп на стандартных сессиях
- Адаптация: HRV < 40 → easy; Sleep < 6ч → убрать интенсивность; ATL/CTL > 1.3 → rest; RHR > 54 несколько дней → лёгкий день
- НЕ leg extension, НЕ выпады в шаге; убрать зал за 10 дней до старта
- Telegram: ≤2000 символов, plain text

---

## Git Log Strategy

Каждый запуск коммитит `data/snapshots/`, `data/reports/`, `data/logs/`, обновлённый `plan/`. Git история = полный хронологический архив всех данных и решений.
