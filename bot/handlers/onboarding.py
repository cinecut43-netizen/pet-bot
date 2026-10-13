"""/start: знакомство и выбор питомца (вид → цвет → имя)."""

from __future__ import annotations

import random

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..db import Database
from ..keyboards import ColorCB, SpeciesCB, care_kb, color_kb, species_kb
from ..render import Look, Renderer
from ..views import send_grid, send_pet

router = Router(name="onboarding")


class NewPet(StatesGroup):
    species = State()
    color = State()
    name = State()


def parse_ref(payload: str | None) -> int | None:
    """start=ref_123 → 123. Всё остальное игнорируем."""
    if payload and payload.startswith("ref_") and payload[4:].isdigit():
        return int(payload[4:])
    return None


def valid_name(raw: str) -> str | None:
    name = " ".join(raw.split())
    if 1 <= len(name) <= 20 and any(ch.isalpha() for ch in name):
        return name
    return None


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext,
                db: Database, renderer: Renderer) -> None:
    user = message.from_user
    ref = parse_ref(command.args)
    is_new = await db.upsert_user(user.id, ref)
    if is_new:
        await db.log_event(user.id, "start", ref=ref, payload=command.args)

    pet = await db.get_pet(user.id)
    if pet:
        await state.clear()
        await message.answer(texts.WELCOME_BACK)
        await send_pet(message.bot, message.chat.id, db, renderer, pet, care_kb())
        return

    await state.set_state(NewPet.species)
    looks = [Look(sp, "ginger", "happy") for sp in renderer.species]
    await send_grid(message.bot, message.chat.id, db, renderer, looks, texts.WELCOME, species_kb(renderer))


@router.callback_query(NewPet.species, SpeciesCB.filter())
async def chose_species(call: CallbackQuery, callback_data: SpeciesCB, state: FSMContext,
                        db: Database, renderer: Renderer) -> None:
    if callback_data.species not in renderer.species:
        await call.answer()
        return
    await state.update_data(species=callback_data.species)
    await state.set_state(NewPet.color)
    looks = [Look(callback_data.species, c, "happy") for c in renderer.colors]
    await call.answer()
    await send_grid(call.bot, call.message.chat.id, db, renderer, looks, texts.CHOOSE_COLOR, color_kb(renderer))


@router.callback_query(NewPet.color, ColorCB.filter())
async def chose_color(call: CallbackQuery, callback_data: ColorCB, state: FSMContext,
                      renderer: Renderer) -> None:
    if callback_data.color not in renderer.colors:
        await call.answer()
        return
    await state.update_data(color=callback_data.color)
    await state.set_state(NewPet.name)
    await call.answer()
    await call.message.answer(texts.ASK_NAME)


@router.message(NewPet.name, F.text, ~F.text.startswith("/"))
async def got_name(message: Message, state: FSMContext, db: Database, renderer: Renderer) -> None:
    name = valid_name(message.text)
    if not name:
        await message.answer(texts.BAD_NAME)
        return
    data = await state.get_data()
    await state.clear()

    # Каждый питомец немного уникален: с шансом 50% у него есть особая черта
    traits = [random.choice(list(renderer.traits))] if random.random() < 0.5 else []
    starter = [k for k, v in renderer.items.items() if v.get("starter")]
    pet = await db.create_pet(message.from_user.id, name, data["species"], data["color"], traits, starter)
    await db.log_event(message.from_user.id, "pet_created", species=pet.species, color=pet.color)

    await send_pet(message.bot, message.chat.id, db, renderer, pet, care_kb(),
                   line=f"Привет! Я {name}. Будем заботиться друг о друге? 🐾")
    await message.answer(
        f"🎁 В гардеробе тебя ждут подарки: {len(starter)} вещи. "
        "Нажми «Гардероб» под картинкой, чтобы примерить.\n\n"
        "Каждый вечер в 19:00 я буду мягко напоминать о себе — настроить можно командой /reminder.\n"
        "Живёшь не по московскому времени? Выбери свой часовой пояс: /timezone"
    )


# Кнопки старого онбординга после перезапуска бота: состояние потеряно — начинаем заново.
@router.callback_query(SpeciesCB.filter())
@router.callback_query(ColorCB.filter())
async def stale_onboarding(call: CallbackQuery) -> None:
    await call.answer("Нажми /start, чтобы начать заново", show_alert=True)
