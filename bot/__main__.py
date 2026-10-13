"""Точка входа: python -m bot"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import load_config
from .db import Database
from .handlers import care, onboarding, settings
from .reminders import reminder_loop
from .render import Renderer

COMMANDS = [
    BotCommand(command="pet", description="Мой питомец"),
    BotCommand(command="wardrobe", description="Гардероб"),
    BotCommand(command="reminder", description="Напоминания"),
    BotCommand(command="help", description="Помощь"),
]


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    db = await Database.connect(cfg.database_url)
    renderer = Renderer(cfg.assets_dir, cfg.cache_dir)

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(db=db, renderer=renderer, admin_ids=cfg.admin_ids)
    dp.include_routers(onboarding.router, care.router, settings.router)

    await bot.set_my_commands(COMMANDS)
    reminders = asyncio.create_task(reminder_loop(bot, db, renderer))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
