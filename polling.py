"""Локальная отладка без публичного HTTPS-адреса: запуск через long polling.

    python polling.py

Использует тот же bot и dp, что и вебхук-сервис.
"""
import asyncio
import logging

from bot.db import init_db
from main import bot, dp, COMMANDS


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(COMMANDS)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
