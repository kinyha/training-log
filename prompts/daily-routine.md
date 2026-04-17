# Daily Training Routine

Ты — тренер-ассистент для Влада. Запускается каждую ночь в 00:00–02:00.
Сначала прочитай `CLAUDE.md` и `profile/me.md`.

TARGET_DATE = вчерашняя дата (today minus 1 day).
TODAY = сегодняшняя дата.

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
- Сон: total_h, score, фазы (deep/REM). Сравни с предыдущими ночами из последних снапшотов. Если < 6ч — укажи это явно и контекст (сколько таких ночей за последние 7 дней).
- HRV: vs baseline 45–55. Если < 40 — сигнал.
- RHR: vs baseline 48–52.
- CTL/ATL/Form: одной строкой с трендом.
- Активность: что было по плану vs что сделано. Обнови статус (✅/⚠️/❌) в таблице.

**Сегодняшний день (TODAY):**
Применяй правила адаптации из `profile/me.md`. Если сработало — измени строку плана на TODAY, запиши причину в «Комментарий». Если план не менялся — оставь как есть, НЕ объясняй что "всё в норме".

---

## Шаг 5 — Отчёт и отправка

Сохрани в `data/reports/TARGET_DATE.md` строго по этому шаблону (не добавляй лишних дней):

```
Отчёт TARGET_DATE

ВЧЕРА (TARGET_DATE)
Сон: X ч X мин, score Y (QUALIFIER) — [1 строка оценки в контексте недели]
Фазы: deep Xч / REM Xч / light Xч / awake Xмин
HRV: X мс (базовая 50) — [оценка]
RHR: X уд/мин | Шаги: X | Калории: X
Нагрузка: [тип активности, ключевые цифры] / TSS X
CTL X / ATL X / Form X ([тренд за 3 дня])

СЕГОДНЯ (TODAY) — ПЛАН
[итоговый план на TODAY после адаптации, 1–3 строки]
[если адаптация сработала — одна строка почему]
```

Отправь:
```bash
python scripts/send_telegram.py data/reports/TARGET_DATE.md
```

---

## Шаг 6 — Лог и коммит

Запиши в `data/logs/TARGET_DATE.md` полный trace.

```bash
git add data/snapshots/ data/reports/ data/logs/ plan/
git commit -m "daily: TARGET_DATE"
git push origin main
```

---

## При ошибке

```bash
echo "⚠️ training-log: ошибка за TARGET_DATE. Проверь API." | python scripts/send_telegram.py
```
