# Claude Code — Training Log

Это персональный тренировочный репозиторий Влада. В начале каждой сессии прочитай этот файл и [`me.md`](me.md), [`goals.md`](goals.md).

## Структура

- Профиль и медицина: [`me.md`](me.md)
- Цели и периодизация: [`goals.md`](goals.md) (секция «Текущий месяц» — свежие объёмы и фокус)
- Программа зала: [`gym-program.md`](gym-program.md) (упражнения, hard limits)
- Протокол веса: [`weight-protocol.md`](weight-protocol.md) (семаглутид, мониторинг)
- Текущая неделя: `weeks/YYYY-WW.md` (ISO-неделя содержащая сегодняшнюю дату)
- Логи тренировок: [`training/gym.md`](training/gym.md), [`training/running.md`](training/running.md)
- Снапшоты: `data/snapshots/YYYY-MM-DD.json`
- Сырые данные: `data/raw/intervals/`, `data/raw/garmin/`
- Архив до 2026-04-23: [`archive/legacy/`](archive/legacy/)
- Спека текущей архитектуры: [`docs/superpowers/specs/2026-04-23-training-log-redesign-design.md`](docs/superpowers/specs/2026-04-23-training-log-redesign-design.md)

## Slash-команды

- [`/training:sync`](.claude/commands/training-sync.md) — догнать данные (intervals.icu + Garmin) до сегодня, обновить активный `weeks/*.md`, `training/gym.md`, `training/running.md`, отправить короткий TG-дайджест.
- [`/training:weekly`](.claude/commands/training-weekly.md) — review прошедшей недели + черновик плана следующей. Запускается в воскресенье.

Обе команды — **ручные**. Ночных рутин нет.

## Critical Rules

### HRV & RHR — поправка на венлафаксин

Влад на венлафаксине 150 мг (SNRI). Baseline смещён фармакологически, **не** овертренировка:
- Нормальный HRV: **45–55 мс** (исторический до препарата был 85 ± 5)
- Нормальный RHR: **48–52 bpm** (исторический 43–44)
- HRV 50 — **не** «низкий». Сравнивать только с venlafaxine-baseline.
- Надёжные маркеры усталости: субъективное самочувствие, часы сна, темп на стандартных сессиях.

### Колено и плечо

- **Никогда** не предлагай leg extension (гонартроз 3 ст.)
- **Никогда** не предлагай выпады шагом (patellofemoral stress)
- Наклонный жим — мониторить при возврате симптомов плеча, при необходимости снять
- Разгибание ног сидя — формально запрещено; если Влад делает — мониторить и фиксировать флаг

### Вес — поправка на семаглутид

Влад на семаглутиде микродозинг (0.16 мг/нед). Смотри [`weight-protocol.md`](weight-protocol.md):
- Вес оценивать по тренду недели (min/max/avg), **не** по отдельным дням
- Креатин 10 г/день удерживает 1–1.5 кг воды — учитывать
- Триггеры пересмотра протокола — в `weight-protocol.md`

### Telegram

- Максимум 4096 символов на сообщение (скрипт чанкает)
- Plain text — избегать `_` или `*` внутри значений метрик
- Язык: русский
- Отправляется только по итогу `/training:sync` или `/training:weekly`, **не** автоматически ночью

### Git

- Slash-команды коммитят локально, **не push без явной просьбы пользователя**
- Стейджить только релевантные директории: `data/ weeks/ training/ README.md goals.md`
- Никогда не использовать `--no-verify`, `--force`, не амендить опубликованные коммиты
- Сообщение коммита: `sync: YYYY-MM-DD (+N days)` или `weekly: review W<WW> + plan W<WW+1>`

## Ручные правки между синхронизациями

Между запусками `/training:sync` Влад сам дописывает:
- Колонка «Заметка» в таблице плана `weeks/YYYY-WW.md`
- Секция «Open questions / заметки» в том же файле
- Детали сессий в `training/gym.md` (веса, ощущения, флаги упражнений)
- Произвольные вопросы к ассистенту в «Open questions»

Claude **не трогает** эти секции при синхронизации. Trust, но verify — если кажется что пользователь мог забыть заполнить, спроси.

## Data Pipeline (упрощённо)

```
scripts/fetch_intervals.py          →  data/raw/intervals/YYYY-MM-DD.json
[Claude: GetFast MCP]               →  data/raw/garmin/YYYY-MM-DD.json
scripts/normalize.py                →  data/snapshots/YYYY-MM-DD.json
scripts/pipeline.py build-summary   →  JSON для сводки недели
[Claude: обновляет weeks/ и training/]
scripts/pipeline.py digest          →  текст TG
scripts/send_telegram.py            →  Telegram
git commit (локально)
```

Полный флоу — в `.claude/commands/training-sync.md`.
