# Steam Market Arbitrage & Liquidity Analyzer

Локальный веб-терминал для анализа предметов Steam Market и поиска выгодных ордеров.

## Возможности
- Отслеживание предметов CS2 (730), Dota 2 (570), Rust (252490), TF2 (440).
- Получение Lowest Sell, Highest Buy Order, объёма за 24ч и медианной цены.
- Расчёт чистой прибыли с учётом комиссии Steam (~13.04%).
- Индекс ликвидности и статусы (Выгодно / Низкая ликвидность / Ожидание).
- Графики истории цен и визуализация стакана заявок (Chart.js).
- Симулятор портфеля с нереализованным профитом.
- Фоновое обновление (APScheduler) с защитой от 429 (jitter 3-5 с, backoff).
- TTL-кэш (60 мин) в SQLite.
- Стартовые данные (seeder) для 5 культовых предметов.

## Стек
- Backend: Python 3.11+, FastAPI, Uvicorn, Pydantic v2
- HTTP: httpx (async), семафор 1 поток, jitter, backoff
- БД: SQLite через aiosqlite
- Планировщик: APScheduler (AsyncIOScheduler)
- Frontend: Jinja2 + Tailwind CSS (CDN) + Chart.js (CDN)

## Запуск
```bash
cd steam-market-analyzer
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Откройте http://127.0.0.1:8000

## Конфигурация (переменные окружения)
- `CURRENCY` — валюта Steam (по умолчанию 5 = RUB)
- `DB_PATH` — путь к БД (по умолчанию steam_market.db)
- `CACHE_TTL_MINUTES` — TTL кэша (по умолчанию 60)
- `RATE_LIMIT_MIN` / `RATE_LIMIT_MAX` — задержка между запросами (3-5 с)
- `SCHEDULER_INTERVAL_MINUTES` — интервал фонового обновления (по умолчанию 5)
- `PROXY` — опциональный HTTP-прокси

## Структура
```
app/
  main.py          # точка входа, lifespan
  config.py        # настройки
  database.py      # SQLite-слой, seeder, логи
  schemas.py       # Pydantic-модели
  scheduler.py     # фоновое обновление
  routers/
    api.py         # REST API
    pages.py       # HTML-страницы
  services/
    steam_client.py  # клиент Steam
    calculator.py    # математика комиссий
  templates/       # Jinja2 шаблоны
scripts/
  bulk_add_dota.py # массовое добавление Dota 2 предметов
```

## Лицензия
MIT — см. [LICENSE](LICENSE).
