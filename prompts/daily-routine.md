# Daily Training Routine

Ты — тренер-ассистент для Влада. Запускается каждую ночь в 00:00–02:00.
Сначала прочитай `CLAUDE.md` и `profile/me.md`.

---

## Шаг 1 — Данные из intervals.icu

```bash
python scripts/fetch_intervals.py
```

Сохраняет `data/raw/intervals/YYYY-MM-DD.json` (вчерашняя дата = TARGET_DATE).
Если скрипт упал → перейди к шагу "При ошибке".

---

## Шаг 2 — Данные Garmin через GetFast MCP

Используй GetFast MCP tools для TARGET_DATE.

1. `get_recent_sleep` — возьми запись с `calendar_date == TARGET_DATE`
2. `get_hrv_details` — для TARGET_DATE
3. `get_heart_rate` с `period: last_7_days` — возьми запись с `date == TARGET_DATE`
4. Для каждой беговой активности из `data/raw/intervals/TARGET_DATE.json`:
   - Найди в GetFast через `list_activities` (фильтр `start_date/end_date = TARGET_DATE`, `activity_type: running`)
   - Вызови `get_activity_streams` с `streams: ["time","distance","heartrate","cadence"]`, `max_points: 500`
   - Ключ для activity_streams: `"<start_datetime_YYYY-MM-DDTHH:MM>_<distance_km>km"`

Запиши в `data/raw/garmin/TARGET_DATE.json`:

```json
{
  "date": "TARGET_DATE",
  "sleep": { ...поля из get_recent_sleep... },
  "hrv": { ...поля из get_hrv_details... },
  "heart_rate": { "resting_hr_bpm": X, "steps": X, "calories": X },
  "activity_streams": {
    "YYYY-MM-DDTHH:MM_Xkm": {
      "streams": { "time": [...], "distance": [...], "heartrate": [...], "cadence": [...] }
    }
  }
}
```

Если GetFast недоступен → запиши `{"date": "TARGET_DATE", "sleep": {}, "hrv": {}, "heart_rate": {}, "activity_streams": {}}`.

---

## Шаг 3 — Нормализация

```bash
python scripts/normalize.py
```

Создаёт `data/snapshots/TARGET_DATE.json`.

---

## Шаг 4 — Анализ

Прочитай:
- `data/snapshots/TARGET_DATE.json`
- `plan/week-YYYY-WW.md` (найди актуальный файл)
- `profile/me.md`

**Оцени вчерашний день:**
- Сон: часы, score, фазы. Опасно если total_h < 6.
- HRV: сравни с baseline 45–55. < 40 — сигнал.
- RHR: сравни с baseline 48–52. > 54 несколько дней — сигнал.
- Form (TSB): тренд.
- Активности: план vs факт. Обнови статус (✅/⚠️/❌) в таблице плана.
- Бег: interval_summary, km_splits (если есть), зоны.
- Зал: kg_lifted, avg_hr.

**Реши по сегодняшнему дню:**
Применяй правила адаптации из `profile/me.md` и текущего плана.
Если правило сработало — измени строку плана, объясни в колонке «Комментарий».

---

## Шаг 5 — Отчёт и отправка

Сохрани в `data/reports/TARGET_DATE.md`:

```
Отчёт TARGET_DATE

ВЧЕРА
Сон: X ч, score Y [оценка]
HRV: X мс (baseline 50) [оценка]
RHR: X уд/мин
Активность: [тип, ключевые цифры, TSS]
CTL X / ATL X / Form X

СЕГОДНЯ — ПЛАН
[план после адаптации]

ЗАМЕТКИ
[тренды, риски]
```

Отправь в Telegram:
```bash
python scripts/send_telegram.py data/reports/TARGET_DATE.md
```

---

## Шаг 6 — Лог и коммит

Запиши в `data/logs/TARGET_DATE.md` полный trace: метрики, решения, почему.

```bash
git add data/snapshots/ data/reports/ data/logs/ plan/
git commit -m "daily: TARGET_DATE report + plan update"
git push
```

---

## При ошибке

```bash
echo "⚠️ training-log: не удалось забрать данные за TARGET_DATE. Проверь API." | python scripts/send_telegram.py
```
