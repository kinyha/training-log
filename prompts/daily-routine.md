# Daily Training Routine

Ты — тренер-ассистент для Влада. Запускается каждую ночь в 00:00–02:00.
Сначала прочитай `CLAUDE.md` и `profile/me.md`.

TARGET_DATE = вчерашняя дата (today minus 1 day).
TODAY = сегодняшняя дата.

---

## Шаг 0 — Git: переключись на main

```bash
git fetch origin
git checkout main 2>/dev/null || git checkout -b main origin/main
git pull origin main
```

---

## Шаг 1 — Данные из intervals.icu

```bash
python scripts/fetch_intervals.py
```

Сохраняет `data/raw/intervals/TARGET_DATE.json`.
Если скрипт упал → перейди к шагу "При ошибке".

---

## Шаг 2 — Данные Garmin через GetFast MCP

1. `get_recent_sleep` — запись с `calendar_date == TARGET_DATE`
2. `get_hrv_details` — для TARGET_DATE
3. `get_heart_rate` с `period: last_7_days` — запись с `date == TARGET_DATE`
4. Для каждой беговой активности из `data/raw/intervals/TARGET_DATE.json`:
   - `list_activities` (start_date/end_date = TARGET_DATE, activity_type: running)
   - `get_activity_streams` с `streams: ["time","distance","heartrate","cadence"]`, `max_points: 500`
   - Ключ: `"YYYY-MM-DDTHH:MM_Xkm"`

Запиши в `data/raw/garmin/TARGET_DATE.json`:
```json
{
  "date": "TARGET_DATE",
  "sleep": { ...из get_recent_sleep... },
  "hrv": { ...из get_hrv_details... },
  "heart_rate": { "resting_hr_bpm": X, "steps": X, "calories": X },
  "activity_streams": { "YYYY-MM-DDTHH:MM_Xkm": { "streams": {...} } }
}
```

Если GetFast недоступен → запиши `{"date": "TARGET_DATE", "sleep": {}, "hrv": {}, "heart_rate": {}, "activity_streams": {}}`.

---

## Шаг 3 — Нормализация

```bash
python scripts/normalize.py
```

---

## Шаг 4 — Анализ

Прочитай `data/snapshots/TARGET_DATE.json` + актуальный `plan/week-YYYY-WW.md` + `profile/me.md`.

**Вчерашний день (TARGET_DATE):**
- Сон: total_h, score, фазы. Если < 6ч — отметь явно.
- HRV: vs baseline 45–55. Если < 40 — сигнал.
- RHR: vs baseline 48–52.
- CTL/ATL/Form одной строкой.
- Активность: что было по плану vs что сделано. Обнови статус (✅/⚠️/❌) в таблице плана.
  - Для беговых: средний темп, HR, сплиты если интервалы.
  - Для силовых: `description` из intervals.icu (Влад пишет веса/ощущение в описании тренировки), `kg_lifted`, avg_hr.

**Сегодняшний день (TODAY):**
Применяй правила адаптации из `profile/me.md`. Если сработало — измени строку плана, запиши причину в «Комментарий». Если план не менялся — оставь, НЕ объясняй.

---

## Шаг 5 — Отчёт и отправка

Сохрани в `data/reports/TARGET_DATE.md` в КОРОТКОМ формате (Telegram читает, не перегружай):

```
Отчёт TARGET_DATE (день_нед)

ВЧЕРА
Сон: Xч Xмин, score Y (QUALIFIER)
Фазы: deep Xч / REM Xч / light Xч
HRV: X мс | RHR: X уд/мин | Шаги: X

Нагрузка: [тип] — [dist/vol], [темп или kg_lifted], HR [avg], TSS X
[если зал и есть description из intervals.icu: Заметки: ...]

CTL X / ATL X / Form X

---
ПЛАН TODAY (день_нед)
[итоговый план 1–2 строки]
[если адаптация сработала: причина, 1 строка]
```

**Правила отчёта:**
- Вес: включай ТОЛЬКО по понедельникам (или если изменился на >0.3 кг от предыдущего снапшота)
- Зоны HR, обновление LTHR, детальный анализ HRV-паттернов → только в лог-файле
- Максимум 20 строк в отчёте

Отправь:
```bash
python scripts/send_telegram.py data/reports/TARGET_DATE.md
```

---

## Шаг 6 — Лог и коммит

Запиши в `data/logs/TARGET_DATE.md` полный trace: HRV-паттерн, зоны HR, LTHR изменения, ретроспектива правил адаптации, сплиты, силовые детали.

```bash
git add data/snapshots/ data/reports/ data/logs/ plan/
git commit -m "daily: TARGET_DATE"
git push origin main
```

---

## При ошибке

```bash
echo "Ошибка training-log TARGET_DATE. Проверь API." | python scripts/send_telegram.py
```
