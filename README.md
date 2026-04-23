# training-log

Персональный репозиторий для ежедневного цикла: сбор метрик (intervals.icu + Garmin), нормализация, формирование отчёта и отправка в Telegram.

## Что уже есть
- Автосбор данных из intervals.icu (`scripts/fetch_intervals.py`).
- Нормализация ежедневного снапшота (`scripts/normalize.py`).
- Отправка отчёта в Telegram с автоматическим чанкингом сообщений (`scripts/send_telegram.py`).
- Набор тестов для пайплайна (`tests/`).
- Операционные промпты для daily/weekly рутины (`prompts/`).

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # если файла нет — создай вручную
pytest -q
```

## Документы
- Спецификация пайплайна: `docs/daily-routine-spec.md`
- Аудит и roadmap улучшений: `docs/repo-improvements-2026-04-23.md`
- Контекст атлета и правила адаптации: `profile/me.md`, `CLAUDE.md`
