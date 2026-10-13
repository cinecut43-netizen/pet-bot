from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .pet import ACTIONS
from .render import Renderer


class SpeciesCB(CallbackData, prefix="sp"):
    species: str


class ColorCB(CallbackData, prefix="col"):
    color: str


class CareCB(CallbackData, prefix="care"):
    action: str
    src: str = "p"  # p — с карточки питомца, r — из напоминания


class WearCB(CallbackData, prefix="wear"):
    item: str


class NavCB(CallbackData, prefix="nav"):
    to: str  # pet / wardrobe


def species_kb(renderer: Renderer) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, sp in renderer.species.items():
        kb.button(text=sp["name"], callback_data=SpeciesCB(species=key))
    kb.adjust(3)
    return kb.as_markup()


def color_kb(renderer: Renderer) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, c in renderer.colors.items():
        kb.button(text=c["name"], callback_data=ColorCB(color=key))
    kb.adjust(3)
    return kb.as_markup()


def care_kb(src: str = "p") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for a in ACTIONS.values():
        kb.button(text=f"{a.emoji} {a.button}", callback_data=CareCB(action=a.key, src=src))
    kb.button(text="👕 Гардероб", callback_data=NavCB(to="wardrobe"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def wardrobe_kb(renderer: Renderer, owned: list[str], equipped: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in owned:
        if item not in renderer.items:
            continue  # вещь убрали из манифеста — просто не показываем
        mark = "✅ " if item in equipped else ""
        kb.button(text=mark + renderer.items[item]["name"], callback_data=WearCB(item=item))
    kb.button(text="⬅️ К питомцу", callback_data=NavCB(to="pet"))
    kb.adjust(2)
    return kb.as_markup()
