# Qada Salah Bot

Телеграм-бот (aiogram 3 + FastAPI, вебхуки) для наверстывания долговых намазов и постов.

## Что умеет

- `/start` — регистрация: указать число лет долга **или** период «с — по». Долг = `лет × 365` дней по каждому из 5 фард-намазов (Фаджр, Зухр, Аср, Магриб, Иша).
- `/fajr`, `/dhuhr`, `/asr`, `/maghrib`, `/isha` — отметить наверстанный намаз. Оптом: `/fajr 10`.
- `/day` — отметить целый день (все намазы +1). Оптом: `/day 5`.
- `/fasts` — задать долг по постам, `/fast` (или `/fast 5`) — отмечать посты.
- `/status` — текущее положение; `/reset` — сброс; `/help` — список команд.

Те же действия доступны кнопками обычной клавиатуры. После каждой отметки бот показывает общий остаток.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # и впиши BOT_TOKEN
```

## Запуск с вебхуком (прод)

Нужен публичный HTTPS-адрес. Заполни в `.env`: `BOT_TOKEN`, `BASE_WEBHOOK_URL`, `WEBHOOK_SECRET`.

```bash
python main.py
# либо: uvicorn main:app --host 0.0.0.0 --port 8080
```

На старте сервис сам выставит вебхук на `BASE_WEBHOOK_URL + WEBHOOK_PATH` и повесит меню команд.
Telegram должен ходить на твой домен по HTTPS (обычно за reverse-proxy, напр. nginx/Caddy).

### Локальная проверка вебхука через ngrok

```bash
ngrok http 8080
# BASE_WEBHOOK_URL в .env = выданный https-адрес ngrok, затем:
python main.py
```

## Локальная отладка без домена (polling)

```bash
python polling.py
```

Удобно для разработки — публичный адрес не нужен.

## Настройки (`.env`)

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `BOT_TOKEN` | токен от @BotFather | — |
| `BASE_WEBHOOK_URL` | публичный HTTPS-адрес; пусто = вебхук не ставится | `` |
| `WEBHOOK_PATH` | путь эндпоинта вебхука | `/webhook` |
| `WEBHOOK_SECRET` | секрет заголовка Telegram | `` |
| `HOST` / `PORT` | адрес uvicorn | `0.0.0.0` / `8080` |
| `DB_PATH` | файл SQLite | `salah.db` |
| `DAYS_PER_YEAR` | дней в году долга | `365` |

Данные хранятся в SQLite (`salah.db`). Состояние регистрации — в памяти (FSM), на отметки долга не влияет.
