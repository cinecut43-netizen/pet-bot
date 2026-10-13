"""Отправка и обновление карточки питомца (картинка + подпись + кнопки).

Каждая уникальная картинка загружается в Telegram один раз: её file_id
сохраняется в render_cache, дальше бот шлёт только file_id.
"""

from __future__ import annotations

import asyncio
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message

from . import texts
from .db import Database, Pet
from .pet import STAT_LABELS, STATS, bar
from .render import Look, Renderer


def look_of(pet: Pet) -> Look:
    return Look(pet.species, pet.color, pet.mood, tuple(pet.traits), tuple(pet.equipped))


def caption(pet: Pet, line: str | None = None) -> str:
    stats = "\n".join(f"{STAT_LABELS[k]}  {bar(pet.stats[k])}" for k in STATS)
    line = line or texts.pick(texts.MOOD_LINES[pet.mood])
    return f"<b>{escape(pet.name)}</b>\n<i>{escape(line)}</i>\n\n{stats}"


async def _photo(db: Database, key: str, make_png) -> str | BufferedInputFile:
    file_id = await db.get_file_id(key)
    if file_id:
        return file_id
    png = await asyncio.to_thread(make_png)
    return BufferedInputFile(png, filename=f"{key}.png")


async def _remember(db: Database, key: str, sent: Message | bool) -> None:
    if isinstance(sent, Message) and sent.photo:
        await db.save_file_id(key, sent.photo[-1].file_id)


async def send_pet(bot: Bot, chat_id: int, db: Database, renderer: Renderer, pet: Pet,
                   kb: InlineKeyboardMarkup, line: str | None = None) -> Message:
    look = look_of(pet)
    key = renderer.cache_key(look)
    photo = await _photo(db, key, lambda: renderer.render_png(look))
    sent = await bot.send_photo(chat_id, photo, caption=caption(pet, line), reply_markup=kb)
    if not isinstance(photo, str):
        await _remember(db, key, sent)
    return sent


async def edit_pet(message: Message, db: Database, renderer: Renderer, pet: Pet,
                   kb: InlineKeyboardMarkup, line: str | None = None, text: str | None = None) -> None:
    """Обновляет существующую карточку. Если сообщение без фото — шлёт новую."""
    if not message.photo:
        await send_pet(message.bot, message.chat.id, db, renderer, pet, kb, line)
        return
    look = look_of(pet)
    key = renderer.cache_key(look)
    photo = await _photo(db, key, lambda: renderer.render_png(look))
    try:
        sent = await message.edit_media(
            InputMediaPhoto(media=photo, caption=text or caption(pet, line)), reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise
        return
    if not isinstance(photo, str):
        await _remember(db, key, sent)


async def send_grid(bot: Bot, chat_id: int, db: Database, renderer: Renderer,
                    looks: list[Look], text: str, kb: InlineKeyboardMarkup) -> None:
    """Картинка-подборка для онбординга (виды или цвета)."""
    key = "grid_" + renderer.grid_key(looks)
    photo = await _photo(db, key, lambda: renderer.grid_png(looks))
    sent = await bot.send_photo(chat_id, photo, caption=text, reply_markup=kb)
    if not isinstance(photo, str):
        await _remember(db, key, sent)
