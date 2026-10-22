import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, Update
from fastapi import FastAPI, Request, Response

from bot.config import settings
from bot.db import init_db
from bot.handlers import router

logging.basicConfig(level=logging.INFO)


class RetryRequestMiddleware(BaseRequestMiddleware):
    """Повторяет исходящие запросы к Telegram при сетевых сбоях/таймаутах.

    Иногда соединение с Bot API зависает и отправка ответа падает с
    TelegramNetworkError. Без повтора пользователь не получит подтверждение
    (хотя отметка в БД уже сделана) и может внести данные повторно. Повторяем
    запрос с новым соединением, чтобы ответ гарантированно дошёл.
    """

    def __init__(self, retries: int = 3, delay: float = 1.0) -> None:
        self.retries = retries
        self.delay = delay

    async def __call__(self, make_request, bot, method):
        for attempt in range(1, self.retries + 1):
            try:
                return await make_request(bot, method)
            except TelegramNetworkError as e:
                if attempt == self.retries:
                    raise
                logging.warning(
                    "Telegram %s: сетевой сбой (попытка %s/%s): %s — повтор через %.1fs",
                    type(method).__name__, attempt, self.retries, e, self.delay * attempt,
                )
                await asyncio.sleep(self.delay * attempt)


# Короткий таймаут на один запрос к Telegram: зависшее соединение быстро
# обрывается, и RetryRequestMiddleware успевает повторить отправку, пока
# Telegram ждёт ответ на вебхук.
REQUEST_TIMEOUT = 15.0

# Необязательное переопределение адреса Telegram Bot API
if settings.tg_api_url:
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(settings.tg_api_url), timeout=REQUEST_TIMEOUT
    )
    logging.info("Telegram API URL overridden: %s", settings.tg_api_url)
else:
    session = AiohttpSession(timeout=REQUEST_TIMEOUT)

session.middleware.register(RetryRequestMiddleware())

bot = Bot(
    token=settings.bot_token,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

COMMANDS = [
    BotCommand(command="start", description="Начать / статус"),
    BotCommand(command="fajr", description="Отметить Фаджр"),
    BotCommand(command="dhuhr", description="Отметить Зухр"),
    BotCommand(command="asr", description="Отметить Аср"),
    BotCommand(command="maghrib", description="Отметить Магриб"),
    BotCommand(command="isha", description="Отметить Иша"),
    BotCommand(command="day", description="Отметить целый день"),
    BotCommand(command="fast", description="Отметить пост"),
    BotCommand(command="undo", description="Отменить последнюю отметку"),
    BotCommand(command="fasts", description="Настроить долг постов"),
    BotCommand(command="edit", description="Изменить долг по дням"),
    BotCommand(command="status", description="Положение"),
    BotCommand(command="reset", description="Сбросить"),
    BotCommand(command="help", description="Помощь"),
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    await bot.set_my_commands(COMMANDS)
    if settings.base_webhook_url:
        url = settings.base_webhook_url.rstrip("/") + settings.webhook_path
        await bot.set_webhook(
            url=url,
            secret_token=settings.webhook_secret or None,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types(),
        )
        logging.info("Webhook set: %s", url)
    else:
        logging.warning("BASE_WEBHOOK_URL пуст — вебхук не выставлен (используй polling.py для отладки)")
    yield
    await bot.delete_webhook()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)

# Защита от повторных вебхуков: при проблемах со связью Telegram может прислать
# один и тот же апдейт несколько раз. Храним уже обработанные update_id и
# игнорируем дубликаты. Размер ограничиваем, чтобы словарь не рос бесконечно.
_MAX_PROCESSED_UPDATES = 1_000
_processed_updates: dict[int, None] = {}


@app.post(settings.webhook_path)
async def telegram_webhook(request: Request) -> Response:
    if settings.webhook_secret:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != settings.webhook_secret:
            return Response(status_code=401)
    update = Update.model_validate(await request.json(), context={"bot": bot})
    if update.update_id in _processed_updates:
        logging.info("Duplicate update ignored: %s", update.update_id)
        return Response(status_code=200)
    _processed_updates[update.update_id] = None
    if len(_processed_updates) > _MAX_PROCESSED_UPDATES:
        # dict сохраняет порядок вставки — удаляем самый старый update_id
        del _processed_updates[next(iter(_processed_updates))]
    try:
        await dp.feed_update(bot, update)
    except Exception:
        # Всегда отвечаем 200: повтор апдейта Telegram'ом всё равно будет
        # отброшен дедупликацией, а отметка в БД уже сделана.
        logging.exception("Update %s failed", update.update_id)
    return Response(status_code=200)


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
