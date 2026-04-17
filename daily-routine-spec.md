# Daily Training Routine — Спецификация для Claude Code

> Цель: ежедневный отчёт в Telegram о предыдущем дне + план на сегодня, с автоматической адаптацией плана под метрики (сон, HRV, нагрузка). Данные хранятся в Git-репозитории, запускается через **Claude Code Routines** (без собственного cron/VPS).

---

## 1. Архитектура (high-level)

```
┌────────────────────────┐
│  Claude Code Routine   │   ← запускается каждое утро ~07:00 на
│  (cloud, Anthropic)    │     инфраструктуре Anthropic
└───────────┬────────────┘
            │
            │ git clone/pull
            ▼
┌────────────────────────┐      ┌──────────────────────┐
│   GitHub repo          │◄────►│  intervals.icu API   │
│   (training-log)       │      │  (activities +       │
│                        │      │   wellness + events) │
│  data/                 │      └──────────────────────┘
│    wellness/           │
│    activities/         │      ┌──────────────────────┐
│    reports/            │────► │  Telegram Bot API    │
│  plan/                 │      │  (sendMessage)       │
│    week-YYYY-WW.md     │      └──────────────────────┘
│  scripts/              │
└────────────────────────┘
```

**Почему так:**
- **Claude Code Routines** — нативная фича для запуска промпта по расписанию на облачной инфре Anthropic. Компьютер может быть выключен. Лимит Pro: 5 routines/день, Max: 15/день. Доступна на `claude.ai/code`.
- **Git-репо** = единственный источник правды. План, отчёты, сырые метрики — всё в версионируемом виде. Легко посмотреть историю, откатить, редактировать руками.
- **intervals.icu API** даёт и completed activities, и wellness (HRV/sleep/RHR), и planned events (твой план тренировок). API ключ берётся в Settings → Developer. Auth: `Authorization: Bearer API_KEY` (basic auth с `API_KEY:KEY` тоже работает).
- **Telegram Bot API** — простой HTTP POST, без SDK.

---

## 2. Стек

| Компонент | Выбор | Почему |
|---|---|---|
| Язык скриптов | Python 3.11+ | Claude Code уверенно с ним работает, `requests` + `python-dotenv` достаточно |
| Данные | JSON + Markdown в Git | Read-friendly, diff-friendly, Claude может и читать, и писать |
| Секреты | GitHub Secrets (для репо) + Claude Code connector secrets | Никаких ключей в коде |
| Запуск | Claude Code Routine (nightly/weekly cadence) | Встроенное, без cron |
| Нотификации | Telegram Bot API (HTTPS) | Минимум движущихся частей |

---

## 3. Структура репозитория

```
training-log/
├── README.md
├── .gitignore
├── .env.example
├── CLAUDE.md                    # инструкции для Claude Code (главное!)
├── scripts/
│   ├── fetch_intervals.py       # качает данные из intervals.icu
│   ├── send_telegram.py         # шлёт сообщение
│   ├── build_report.py          # собирает отчёт + план (вызывает Claude?)
│   └── lib/
│       ├── intervals_client.py
│       └── telegram_client.py
├── data/
│   ├── wellness/
│   │   └── 2026-04-16.json      # один файл на день
│   ├── activities/
│   │   └── 2026-04-16.json
│   └── reports/
│       └── 2026-04-16.md        # отчёт, отправленный в Telegram
├── plan/
│   ├── week-2026-16.md          # план на текущую неделю
│   └── archive/
│       └── week-2026-15.md
└── prompts/
    └── daily-routine.md         # промпт для самой Claude Code Routine
```

---

## 4. Формат данных

### 4.1 `data/wellness/YYYY-MM-DD.json`

Прямо из intervals.icu `GET /api/v1/athlete/{id}/wellness/{date}`, ключевые поля:

```json
{
  "id": "2026-04-15",
  "restingHR": 48,
  "hrv": 72,
  "sleepSecs": 27000,
  "sleepScore": 82,
  "sleepQuality": 3,
  "readiness": 78,
  "ctl": 65.2,
  "atl": 58.1,
  "ctlLoad": 62,
  "atlLoad": 45,
  "weight": 74.3,
  "soreness": 2,
  "fatigue": 2,
  "stress": 1,
  "mood": 4
}
```

### 4.2 `data/activities/YYYY-MM-DD.json`

Массив активностей за день:

```json
[
  {
    "id": 123456789,
    "start_date_local": "2026-04-15T07:30:00",
    "type": "Run",
    "name": "Easy Run",
    "distance": 10200,
    "moving_time": 3060,
    "icu_training_load": 58,
    "icu_intensity": 72,
    "average_heartrate": 142,
    "average_pace": 5.0
  }
]
```

### 4.3 `plan/week-YYYY-WW.md`

Человекочитаемый план, который ты сам редактируешь руками + Claude может корректировать:

```markdown
# Неделя 16 (13–19 апреля 2026)

**Цель недели:** закладка аэробной базы перед Сожским полумарафоном.
Объём: ~45 км. Ключевая тренировка — темпо 8 км @ 4:30.

| День       | План                                  | Статус | Комментарий |
|------------|---------------------------------------|--------|-------------|
| Пн 13.04   | Easy 8km @ 5:10                       | ✅      | HRV 68, нормально |
| Вт 14.04   | Gym A (присед/жим)                    | ✅      |             |
| Ср 15.04   | Темпо 2x4km @ 4:30 (2min rest)        | ⚠️      | Перенесено на чт — RHR +6 |
| Чт 16.04   | Easy 10km + strides                   | 🔜      |             |
| Пт 17.04   | Rest или Gym B                        |        |             |
| Сб 18.04   | Long 16km easy                        |        |             |
| Вс 19.04   | Пул 1500m или Rest                    |        |             |

**Правила адаптации (для Claude):**
- HRV < baseline−15% → заменить качество на easy, сдвинуть long
- Sleep < 6h → убрать интенсивность, оставить объём на easy
- ATL/CTL > 1.3 → добавить rest day
```

### 4.4 `data/reports/YYYY-MM-DD.md`

Сам отчёт, который улетел в Telegram (архив):

```markdown
# Отчёт 16.04.2026

## Вчера (15.04)
- Сон: 7ч 30м, score 82 ✅
- HRV: 72 (baseline 70) ✅
- RHR: 48 (норма)
- Активность: Темпо 2x4km @ 4:28 — план выполнен
- TL за день: 72, ATL 58 / CTL 65 → form −7 (лёгкая усталость)

## Сегодня (16.04) — план
Easy 10km + 4x strides по 100м в конце.
Темп 5:10–5:20, пульс до Z2.

## Заметки
ATL ползёт вверх. Если в пт HRV просядет — перенести long на вс.
```

---

## 5. Ключевые скрипты

### 5.1 `scripts/fetch_intervals.py`

```python
"""
Качает за вчерашний день: wellness + activities + planned events.
Сохраняет в data/.
"""
import os, json, sys
from datetime import date, timedelta
from pathlib import Path
import requests

ATHLETE_ID = os.environ["INTERVALS_ATHLETE_ID"]
API_KEY = os.environ["INTERVALS_API_KEY"]
BASE = "https://intervals.icu/api/v1"
AUTH = ("API_KEY", API_KEY)  # HTTP Basic

def fetch(path, params=None):
    r = requests.get(f"{BASE}{path}", auth=AUTH, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    target = date.today() - timedelta(days=1)
    d = target.isoformat()

    wellness = fetch(f"/athlete/{ATHLETE_ID}/wellness/{d}")
    activities = fetch(
        f"/athlete/{ATHLETE_ID}/activities",
        {"oldest": d, "newest": d}
    )

    Path("data/wellness").mkdir(parents=True, exist_ok=True)
    Path("data/activities").mkdir(parents=True, exist_ok=True)

    Path(f"data/wellness/{d}.json").write_text(
        json.dumps(wellness, indent=2, ensure_ascii=False)
    )
    Path(f"data/activities/{d}.json").write_text(
        json.dumps(activities, indent=2, ensure_ascii=False)
    )
    print(f"OK: fetched {d}")

if __name__ == "__main__":
    main()
```

### 5.2 `scripts/send_telegram.py`

```python
"""Шлёт произвольный Markdown в чат."""
import os, sys, requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(text: str):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()

if __name__ == "__main__":
    text = sys.stdin.read()
    send(text)
```

### 5.3 `scripts/build_report.py`

Здесь две опции:

**Вариант A — тупой build (без LLM):** шаблон Jinja2 по метрикам → markdown.
Плюс: дёшево, детерминированно. Минус: не адаптирует план.

**Вариант B — через Claude Code Routine:** сам промпт (см. п.6) читает данные и пишет отчёт. Скрипт только качает данные + коммитит в git. Отчёт и адаптацию делает Claude внутри routine.

**Рекомендую B** — иначе смысл использовать Claude Code.

---

## 6. Промпт для Claude Code Routine

Это главный артефакт. Сохранить в `prompts/daily-routine.md` в репо.

```markdown
# Daily Training Routine Prompt

Ты — мой тренер-ассистент. Каждое утро выполняй следующий workflow.

## Шаг 1. Забрать данные
Запусти `python scripts/fetch_intervals.py`.
Это создаст/обновит `data/wellness/<вчера>.json` и
`data/activities/<вчера>.json`.

## Шаг 2. Проанализировать вчерашний день
Прочитай:
- `data/wellness/<вчера>.json` — сон, HRV, RHR, readiness, ATL/CTL
- `data/activities/<вчера>.json` — что реально сделал
- `plan/week-<текущая-неделя>.md` — что было запланировано

Сравни план с фактом. Обнови статусы (✅/⚠️/❌) в таблице плана.

## Шаг 3. Принять решение по сегодняшнему дню
Примени правила адаптации из `plan/week-*.md`:
- HRV < baseline−15% → заменить качество на easy
- Sleep < 6h → убрать интенсивность
- ATL/CTL > 1.3 → rest day
- RHR +7 от baseline → лёгкий день

Если правило сработало — измени строку плана на сегодня и объясни почему
в колонке «Комментарий». Если всё ок — план не трогай.

## Шаг 4. Сформировать отчёт
Сохрани отчёт в `data/reports/<сегодня>.md` по шаблону:

# Отчёт <сегодня>

## Вчера
- Сон, HRV, RHR (с оценкой relative to baseline)
- Активности (план vs факт)
- TL/ATL/CTL, тренд формы

## Сегодня — план
<итоговый план после адаптации, если была>

## Заметки
<что заметил: тренды, риски, что отслеживать>

## Шаг 5. Отправить в Telegram
```bash
cat data/reports/<сегодня>.md | python scripts/send_telegram.py
```

## Шаг 6. Закоммитить изменения
```bash
git add data/ plan/
git commit -m "daily: <сегодня> report + plan update"
git push
```

## Правила
- НЕ выдумывай метрики. Если какого-то поля нет в JSON — пиши «н/д».
- Не превышай 2000 символов в Telegram-сообщении.
- Все решения по адаптации плана — явные, с объяснением.
- Если API intervals.icu недоступен — отправь в Telegram короткое
  «Не смог забрать данные, проверь API» и выйди.
```

---

## 7. Секреты и конфиг

### 7.1 `.env.example`

```bash
INTERVALS_ATHLETE_ID=iXXXXX
INTERVALS_API_KEY=...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

### 7.2 Где хранить секреты для Routine

Claude Code Routine имеет доступ к connectors и секретам, настроенным в
`claude.ai/code`. Варианты:

1. **Самый простой:** секреты хранятся в GitHub Secrets. В routine перед
   запуском делается `gh secret list` → экспорт в env. Работает, если
   routine имеет доступ к репо через GitHub App (его всё равно нужно
   ставить для push).
2. **Через Claude Code env vars:** задать в настройках routine env-переменные
   напрямую (проверь UI на `claude.ai/code` — там есть secrets на routine).

Чего **не делать**: коммитить `.env` (добавь в `.gitignore` сразу).

---

## 8. Как получить ключи

### 8.1 intervals.icu
1. `intervals.icu` → Settings → Developer Settings
2. Generate API key
3. Athlete ID видно там же (формат `iNNNNN`)

### 8.2 Telegram
1. Написать `@BotFather` → `/newbot` → получить token
2. Написать своему боту любое сообщение (он должен тебя «увидеть»)
3. `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"` → взять `chat.id`

---

## 9. Настройка Claude Code Routine

1. Создать репо `training-log` на GitHub, запушить скелет.
2. В Claude Code Desktop или на `claude.ai/code`:
   - `/schedule` (CLI) или UI → New routine
   - Cadence: **daily at 07:00 local** (Europe/Minsk)
   - Repo: твой `training-log`
   - Prompt: содержимое `prompts/daily-routine.md`
   - Env vars: четыре ключа из `.env.example`
3. Разрешения routine: чтение репо, write (для push), execute bash, network
   (для API вызовов).

**Важно:** routines живут на Pro/Max/Team. Pro — 5 запусков/день, один daily
тратит 1 запуск. Запасы есть.

---

## 10. Что делать дальше самому (ты сказал "остальное сам")

Задачи, которые берёшь на себя после получения отчёта:
- Смотришь ветку / PR если что-то странное в коммите Claude
- Редактируешь `plan/week-*.md` руками в начале недели (воскресный
  планёрочный ритуал)
- Если адаптация Claude не нравится — откатываешь коммит, пишешь новое
  правило в план

Это и есть «human-in-the-loop»: Claude не владеет планом, он его
_модифицирует по твоим правилам_.

---

## 11. Подводные камни

- **Timezone.** intervals.icu отдаёт local time активностей, но wellness — по
  `date`. Убедись, что routine крутится в Europe/Minsk (проверь в UI).
- **7-дневный expiry Claude Code scheduled tasks** относится к сессионным
  `/loop`, **не к routines.** Routines живут пока не отключишь.
- **Rate limits intervals.icu** мягкие, но не спамь — один pull в день хватит.
- **Telegram parse_mode=Markdown** ломается на `_` и `*` внутри значений.
  Либо `MarkdownV2` с экранированием, либо plain text.
- **Git push from routine** — нужен GitHub App установленный на репо, либо
  fine-grained PAT в env.
- **Недостающие wellness-поля.** Если не синхронизировал Garmin в этот день,
  HRV/sleep будут `null` — скрипт должен это переживать.
- **Baseline для HRV** intervals.icu хранит как `hrvSDNNBaseline` или
  считается сам — перепроверь поле в ответе API.

---

## 12. MVP-чеклист

- [ ] Создать репо
- [ ] Получить intervals.icu API key + athlete ID
- [ ] Создать Telegram-бота, узнать chat_id
- [ ] Закинуть скелет (scripts/, data/, plan/, CLAUDE.md)
- [ ] Написать первый `plan/week-XX.md` руками
- [ ] Проверить `fetch_intervals.py` локально (Python + `.env`)
- [ ] Проверить `send_telegram.py` локально
- [ ] Создать routine в Claude Code с промптом
- [ ] Прогнать в ручном режиме один раз (`Run now`)
- [ ] Если всё ок — включить daily cadence

---

## 13. Первые команды для Claude Code

Когда репо готов, в Claude Code открыть проект и сказать:

```
Прочитай spec в README.md и CLAUDE.md. Создай scripts/fetch_intervals.py,
scripts/send_telegram.py и scripts/lib/*. Следуй форматам данных из
секции 4. Не трогай plan/ — я его сам заполню. Минимум зависимостей:
requests, python-dotenv. Добавь requirements.txt.
```

Это стартовый шаг. Когда скрипты будут готовы и протестированы —
настраивай routine по п.9.
