# Steam Market Arbitrage & Liquidity Analyzer

Локальное веб-приложение для анализа предметов Steam Market и поиска выгодных ордеров.

## Запуск

```bash
cd steam-market-analyzer
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Откройте http://127.0.0.1:8000

## Конфигурация

Переменные окружения (опционально):
- `CURRENCY` (по умолчанию 5 = RUB)
- `DB_PATH` (по умолчанию steam_market.db)
- `RATE_LIMIT_DELAY` (сек, по умолчанию 2.5)
- `PROXY` (http прокси)

## Структура
- app/main.py — точка входа
- app/config.py — настройки
- app/database.py — SQLite слой
- app/schemas.py — Pydantic модели
- app/services/steam_client.py — клиент Steam
- app/services/calculator.py — математика комиссий
- app/scheduler.py — фоновое обновление
- app/routers/api.py — REST API
- app/routers/pages.py — HTML страницы
- app/templates/ — Jinja2 шаблоны
