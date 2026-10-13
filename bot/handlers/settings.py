"""/reminder, /timezone, /privacy, /delete_me, /help и /stats (только для админов)."""

from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..db import Database
from ..keyboards import DeleteCB, TzCB, delete_kb, timezone_kb
from ..regions import TIMEZONES, tz_label

router = Router(name="settings")


@router.message(Command("reminder"))
async def reminder(message: Message, command: CommandObject, db: Database) -> None:
    arg = (command.args or "").strip().lower()
    uid = message.from_user.id
    if arg in ("off", "выкл", "нет"):
        await db.set_reminder(uid, enabled=False)
        await message.answer(texts.REMINDER_OFF)
        return
    if arg in ("on", "вкл", "да"):
        await db.set_reminder(uid, enabled=True)
    elif arg.isdigit() and 0 <= int(arg) <= 23:
        await db.set_reminder(uid, enabled=True, hour=int(arg))
    else:
        enabled, hour, tz = await db.get_reminder(uid)
        state = f"каждый день в {hour}:00 ({tz_label(tz)})" if enabled else "выключены"
        await message.answer(f"Сейчас: {state}.\n\n{texts.REMINDER_HELP}")
        return
    _, hour, tz = await db.get_reminder(uid)
    await message.answer(texts.REMINDER_ON.format(hour=hour, tz=tz_label(tz)))


@router.message(Command("timezone"))
async def timezone(message: Message, db: Database) -> None:
    _, _, tz = await db.get_reminder(message.from_user.id)
    await message.answer(texts.TIMEZONE_ASK.format(tz=tz_label(tz)), reply_markup=timezone_kb(tz))


@router.callback_query(TzCB.filter())
async def timezone_chosen(call: CallbackQuery, callback_data: TzCB, db: Database) -> None:
    if callback_data.key not in TIMEZONES:
        await call.answer()
        return
    tz = TIMEZONES[callback_data.key][0]
    await db.set_timezone(call.from_user.id, tz)
    _, hour, _ = await db.get_reminder(call.from_user.id)
    await call.answer()
    await call.message.edit_text(texts.TIMEZONE_SET.format(tz=tz_label(tz), hour=hour))


@router.message(Command("privacy"))
async def privacy(message: Message, privacy_contact: str) -> None:
    contact = texts.PRIVACY_CONTACT.format(contact=escape(privacy_contact)) if privacy_contact else ""
    await message.answer(texts.PRIVACY.format(contact=contact))


@router.message(Command("delete_me"))
async def delete_me(message: Message) -> None:
    await message.answer(texts.DELETE_CONFIRM, reply_markup=delete_kb())


@router.callback_query(DeleteCB.filter())
async def delete_confirmed(call: CallbackQuery, callback_data: DeleteCB,
                           state: FSMContext, db: Database) -> None:
    await call.answer()
    if not callback_data.confirm:
        await call.message.edit_text(texts.DELETE_CANCEL)
        return
    await state.clear()
    deleted = await db.delete_user(call.from_user.id)
    await call.message.edit_text(texts.DELETE_DONE if deleted else texts.DELETE_NOTHING)


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
