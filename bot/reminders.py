"""Мягкое напоминание раз в день от лица питомца.

Проверка раз в минуту; кому пора — решает SQL (см. Database.due_reminders).
Напоминаем только тем, кто сегодня ещё ничего не отметил.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from . import texts
from .db import Database
from .keyboards import care_kb
from .render import Renderer
from .views import send_pet

log = logging.getLogger(__name__)


async def send_due(bot: Bot, db: Database, renderer: Renderer) -> int:
    sent = 0
    for user_id, name in await db.due_reminders():
        # Отмечаем заранее: лучше пропустить одно напоминание, чем прислать два.
        await db.mark_reminded(user_id)
        pet = await db.get_pet(user_id)
        if pet is None:
            continue
        line = texts.pick(texts.REMINDERS).format(name=name)
        try:
            await send_pet(bot, user_id, db, renderer, pet, care_kb(src="r"), line=line)
        except TelegramForbiddenError:
            await db.mark_blocked(user_id)
            continue
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            continue
        except Exception:
            log.exception("reminder to %s failed", user_id)
            continue
        await db.log_event(user_id, "reminder_sent")
        sent += 1
        await asyncio.sleep(0.05)  # ~20 сообщений в секунду, с запасом от лимитов Telegram
    return sent


async def reminder_loop(bot: Bot, db: Database, renderer: Renderer, interval: int = 60) -> None:
    while True:
        try:
            n = await send_due(bot, db, renderer)
            if n:
                log.info("reminders sent: %s", n)
        except Exception:
            log.exception("reminder loop error")
        await asyncio.sleep(interval)
