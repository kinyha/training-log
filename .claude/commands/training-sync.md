---
description: Догнать данные (intervals.icu + Garmin) до сегодня, обновить активный weeks/*.md, training/gym.md, training/running.md, отправить TG-дайджест
---

# /training:sync — догнать данные

Ты — тренер-ассистент Влада. Эта команда запускается вручную раз в 1–3 дня.
Сначала прочитай [`CLAUDE.md`](../../CLAUDE.md), [`me.md`](../../me.md), [`goals.md`](../../goals.md).

**TODAY** = сегодняшняя дата.
**TARGET_DATES** = `[LAST_SYNCED_DATE + 1 … TODAY]`, где `LAST_SYNCED_DATE` = max(`data/snapshots/*.json` по имени файла).

Если диапазон пустой (уже есть снапшот на сегодня) — сразу шаг 6 (пересобрать сводку + дайджест).

---

## Шаг 0 — Git

```bash
git fetch origin
git status --short
```

Если есть неотпушенные локальные изменения — сказать пользователю и дождаться решения (push, discard, проигнорировать). Не затирать чужие правки.

---

## Шаг 1 — intervals.icu

Для каждой даты D в TARGET_DATES:

```bash
python scripts/fetch_intervals.py --date D
```

Сохраняет `data/raw/intervals/D.json`. Если скрипт упал на какой-то дате — зафиксируй, продолжай с остальными, отметь в дайджесте.

---

## Шаг 2 — Garmin через GetFast MCP

Для каждой даты D в TARGET_DATES:

1. `mcp__claude_ai_GetFast__context_get_recent_sleep` — найди запись с `calendar_date == D`
2. `mcp__claude_ai_GetFast__context_get_hrv_details` для D
3. `mcp__claude_ai_GetFast__context_get_heart_rate` с `period: last_7_days` — запись с `date == D`
4. Для каждой беговой активности из `data/raw/intervals/D.json`:
   - `mcp__claude_ai_GetFast__context_list_activities` (`start_date`/`end_date` = D, `activity_type: running`)
   - `mcp__claude_ai_GetFast__context_get_activity_streams` (`streams: ["time","distance","heartrate","cadence"]`, `max_points: 500`)
   - Ключ: `"YYYY-MM-DDTHH:MM_Xkm"`

Запиши в `data/raw/garmin/D.json`:
```json
{
  "date": "D",
  "sleep": { ... },
  "hrv": { ... },
  "heart_rate": { "resting_hr_bpm": X, "steps": X, "calories": X },
  "activity_streams": { "YYYY-MM-DDTHH:MM_Xkm": { "streams": {...} } }
}
```

Если GetFast вернул `ENTITLEMENT_DENIED` — зафиксируй, запиши пустой блок `{"date": "D", "sleep": {}, "hrv": {}, "heart_rate": {}, "activity_streams": {}}`, отметь в дайджесте.

---

## Шаг 3 — Нормализация

Для каждой даты D в TARGET_DATES:

```bash
python scripts/normalize.py --date D
```

Создаёт `data/snapshots/D.json`.

---

## Шаг 4 — Обновить недельный файл `weeks/YYYY-WW.md`

1. Определи активную ISO-неделю по TODAY: `YYYY-WW`.
2. Если файл `weeks/YYYY-WW.md` не существует — создай из шаблона (см. `docs/superpowers/specs/2026-04-23-training-log-redesign-design.md` §4.2). План сессий на пустые дни — из `me.md` baseline, скорректирован по `goals.md` (периодизация, текущий месяц).
3. Для каждой даты D в TARGET_DATES обнови строку таблицы «План и статус»:
   - **Статус:** ✅ если сделано и совпадает с планом, ⚠️ если частично/изменено, ❌ если пропущено без замены
   - **Факт:** короткая сводка (бег: `«10.2 км @ 5:25, HR 132»`; зал: `«1:50, ЧСС 109/153, kg 12500»`)
4. **Колонки «План» и «Заметка» НЕ ТРОГАЙ.** Ими владеет пользователь.

### Шаг 4a — Добавить сессии в training-логи

**Для каждой зальной сессии в TARGET_DATES** (`activities[].type == "Strength"`):
- Открой `training/gym.md`
- Найди секцию `## Неделя <NN>` текущей ISO-недели (создай если нет — используй формат `## Неделя 17 · 20 — 26 апр 2026`)
- Добавь подзаголовок `### Пн YYYY-MM-DD — Gym X` с метриками из снапшота (длительность, ЧСС, TSS, kg_lifted) + `description` из intervals.icu если есть (обычно Влад пишет туда веса и ощущения)
- **Оставь место для ручных деталей** — не придумывай веса, только приведи то что есть в description

**Для каждой беговой сессии в TARGET_DATES:**
- Открой `training/running.md`
- Найди секцию соответствующей недели
- Добавь строку в таблицу с дата/тип/дист/время/темп/ЧСС/TSS/HRV/заметки из снапшота

---

## Шаг 5 — Пересобрать секцию «Сводка» в `weeks/YYYY-WW.md`

Между маркерами `<!-- summary-start -->` и `<!-- summary-end -->` замени содержимое на:

```
**Тренировки:** <done>/<planned> сделано (<краткий перечень>)
**Бег:** <км> из <план> плановых | Z1+Z2%: <процент>
**Зал:** <сессий> / <план> | kg_lifted <сумма>
**Форма:** CTL <X> / ATL <Y> / TSB <Z> (<интерпретация>)
**Сон среднее:** <X>ч | **HRV:** <мс> | **RHR:** <bpm>
**Вес:** <кг> (<тренд недели если есть>)
**Последнее обновление:** <TODAY>
```

Правила:
- Вес включай всегда, тренд — только если на неделе ≥ 3 замеров
- CTL/ATL/TSB из последнего снапшота в диапазоне
- Z1+Z2% считаем по сумме `hr_zone_times_s` во всех беговых сессиях недели

Не трогай ничего вне summary-маркеров.

---

## Шаг 6 — Обновить README.md

Скопируй содержимое `weeks/YYYY-WW.md` между маркерами `<!-- current-week-start -->` и `<!-- current-week-end -->` в `README.md`. Если файл недели длинный — урезай секцию «Open questions» и «Review» (первые 5 строк или опусти).

---

## Шаг 7 — Telegram дайджест

Сформируй текст ≤ 25 строк, ≤ 4000 символов, plain text, без markdown-символов в значениях метрик:

```
Sync <TODAY> (+<N> дней)

НЕДЕЛЯ <WW> (<Пн–Вс>)
Сделано: <done>/<total> (<список>)
Осталось: <что впереди>

ФАКТ ЗА <N> ДНЕЙ
<для каждой даты в TARGET_DATES одна строка с самым важным>

ТЕЛО
Сон ср: <X>ч | HRV: <range> | RHR: <range>
Вес: <X>кг (<дельта vs начало недели>)
CTL <X> / ATL <Y> / TSB <Z> (<интерпретация>)

ФЛАГИ (если есть)
⚠️ <дата> — <что отметил>
```

Отправь:

```bash
python scripts/send_telegram.py --file <временный файл с дайджестом>
```

Если `--no-tg` флаг был в запросе команды пользователя — пропусти отправку.

---

## Шаг 8 — Git коммит

```bash
git add data/ weeks/ training/ README.md
git commit -m "sync: <TODAY> (+<N> days)"
```

**Не push** без явной просьбы пользователя. Сообщи ему: «Закоммитил N файлов локально. Push?»

---

## При ошибке на любом шаге

- Зафиксируй что упало и на какой дате.
- Продолжай с остальными датами если возможно.
- В TG-дайджесте укажи раздел «ОШИБКИ» с коротким описанием.
- Не затирай существующие файлы — только аппендь / обновляй через маркеры.

---

## Переменные окружения (из `.env`)

```
INTERVALS_API_KEY=<ключ>
INTERVALS_ATHLETE_ID=<id>
TELEGRAM_BOT_TOKEN=<токен>
TELEGRAM_CHAT_ID=<chat_id>
```
