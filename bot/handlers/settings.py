"""/reminder, /help и /stats (только для админов)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .. import texts
from ..db import Database

router = Router(name="settings")


@router.message(Command("reminder"))
async def reminder(message: Message, command: CommandObject, db: Database) -> None:
    arg = (command.args or "").strip().lower()
    uid = message.from_user.id
    if arg in ("off", "выкл", "нет"):
        await db.set_reminder(uid, enabled=False)
        await message.answer(texts.REMINDER_OFF)
    elif arg in ("on", "вкл", "да"):
        await db.set_reminder(uid, enabled=True)
        _, hour = await db.get_reminder(uid)
        await message.answer(texts.REMINDER_ON.format(hour=hour))
    elif arg.isdigit() and 0 <= int(arg) <= 23:
        await db.set_reminder(uid, enabled=True, hour=int(arg))
        await message.answer(texts.REMINDER_ON.format(hour=int(arg)))
    else:
        enabled, hour = await db.get_reminder(uid)
        state = f"Сейчас: {'каждый день в ' + str(hour) + ':00' if enabled else 'выключены'}."
        await message.answer(f"{state}\n\n{texts.REMINDER_HELP}")


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(texts.HELP)


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "—"


@router.message(Command("stats"))
async def stats(message: Message, db: Database, admin_ids: frozenset[int]) -> None:
    if message.from_user.id not in admin_ids:
        return
    m = await db.metrics()
    await message.answer(
        "<b>Метрики</b>\n"
        f"Пользователей: {m['users']}, питомцев: {m['pets']}\n"
        f"Активны за 24 ч: {m['active_24h']}\n\n"
        f"<b>D7 сами, без напоминания:</b> {m['d7_self']}/{m['d7_cohort']} = "
        f"{_pct(m['d7_self'], m['d7_cohort'])}\n"
        f"D7 любое дело: {_pct(m['d7_any'], m['d7_cohort'])}\n\n"
        f"Пришли по приглашению: {m['referred']}, пригласивших: {m['inviters']} "
        f"({_pct(m['inviters'], m['pets'])} от всех)\n"
        "<i>Цель концепции: обе главные цифры выше 10–15%.</i>"
    )
