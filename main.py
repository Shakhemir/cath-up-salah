import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, Update
from fastapi import FastAPI, Request, Response

from bot.config import settings
from bot.db import init_db
from bot.handlers import router

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=settings.bot_token,
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


@app.post(settings.webhook_path)
async def telegram_webhook(request: Request) -> Response:
    if settings.webhook_secret:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != settings.webhook_secret:
            return Response(status_code=401)
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return Response(status_code=200)


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port)
