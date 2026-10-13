"""Карточка питомца, кнопки дел и гардероб."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..db import Database
from ..keyboards import CareCB, NavCB, WearCB, care_kb, wardrobe_kb
from ..pet import ACTIONS
from ..render import Renderer
from ..views import edit_pet, send_pet

router = Router(name="care")


@router.message(Command("pet"))
async def show_pet(message: Message, db: Database, renderer: Renderer) -> None:
    pet = await db.get_pet(message.from_user.id)
    if not pet:
        await message.answer(texts.NO_PET)
        return
    await send_pet(message.bot, message.chat.id, db, renderer, pet, care_kb())


@router.callback_query(CareCB.filter())
async def do_care(call: CallbackQuery, callback_data: CareCB, db: Database, renderer: Renderer) -> None:
    if callback_data.action not in ACTIONS:
        await call.answer()
        return
    result = await db.care(call.from_user.id, callback_data.action, from_reminder=callback_data.src == "r")
    if result.status == "no_pet":
        await call.answer(texts.NO_PET, show_alert=True)
        return
    if result.status == "limit":
        await call.answer(texts.LIMIT_REACHED[callback_data.action], show_alert=True)
        return

    reaction = texts.pick(texts.ACTION_REACTIONS[callback_data.action])
    await call.answer(reaction)
    await edit_pet(call.message, db, renderer, result.pet, care_kb(), line=reaction)


@router.message(Command("wardrobe"))
async def wardrobe_cmd(message: Message, db: Database, renderer: Renderer) -> None:
    pet = await db.get_pet(message.from_user.id)
    if not pet:
        await message.answer(texts.NO_PET)
        return
    owned = await db.owned_items(message.from_user.id)
    if not owned:
        await message.answer(texts.WARDROBE_EMPTY)
        return
    await send_pet(message.bot, message.chat.id, db, renderer, pet,
                   wardrobe_kb(renderer, owned, pet.equipped), line=texts.WARDROBE_TITLE)


@router.callback_query(NavCB.filter())
async def navigate(call: CallbackQuery, callback_data: NavCB, db: Database, renderer: Renderer) -> None:
    pet = await db.get_pet(call.from_user.id)
    if not pet:
        await call.answer(texts.NO_PET, show_alert=True)
        return
    await call.answer()
    if callback_data.to == "wardrobe":
        owned = await db.owned_items(call.from_user.id)
        await edit_pet(call.message, db, renderer, pet,
                       wardrobe_kb(renderer, owned, pet.equipped), line=texts.WARDROBE_TITLE)
    else:
        await edit_pet(call.message, db, renderer, pet, care_kb())


@router.callback_query(WearCB.filter())
async def wear(call: CallbackQuery, callback_data: WearCB, db: Database, renderer: Renderer) -> None:
    if callback_data.item not in renderer.items:
        await call.answer()
        return
    slots = {k: v["slot"] for k, v in renderer.items.items()}
    equipped = await db.toggle_item(call.from_user.id, callback_data.item, slots)
    if equipped is None:
        await call.answer("Этой вещи у тебя пока нет", show_alert=True)
        return
    await call.answer()
    pet = await db.get_pet(call.from_user.id)
    owned = await db.owned_items(call.from_user.id)
    await edit_pet(call.message, db, renderer, pet,
                   wardrobe_kb(renderer, owned, equipped), line=texts.WARDROBE_TITLE)
