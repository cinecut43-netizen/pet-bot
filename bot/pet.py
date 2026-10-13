"""Логика питомца: шкалы, дела, настроение. Чистые функции — без БД и Telegram.

Принцип: питомец никогда не умирает и не наказывает. Шкалы плавно убывают
со временем, дела их пополняют, настроение — среднее по шкалам.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

STATS = ("hydration", "energy", "mind", "rest")
DECAY_PER_HOUR = 2.0  # со 100 до 0 примерно за двое суток
MAX_STAT = 100


@dataclass(frozen=True)
class Action:
    key: str
    stat: str
    gain: int
    daily_limit: int
    emoji: str
    button: str


ACTIONS: dict[str, Action] = {
    a.key: a
    for a in (
        Action("water", "hydration", 15, 8, "💧", "Вода"),
        Action("move", "energy", 35, 3, "🏃", "Движение"),
        Action("read", "mind", 35, 3, "📖", "Чтение"),
        Action("sleep", "rest", 60, 1, "😴", "Сон"),
    )
}

STAT_LABELS = {
    "hydration": "💧 Сытость",
    "energy": "🏃 Бодрость",
    "mind": "📖 Ум",
    "rest": "😴 Сон",
}


def decay(stats: dict[str, int], updated_at: datetime, now: datetime) -> dict[str, int]:
    hours = max(0.0, (now - updated_at).total_seconds() / 3600)
    loss = DECAY_PER_HOUR * hours
    return {k: max(0, round(stats[k] - loss)) for k in STATS}


def apply_action(stats: dict[str, int], action: Action) -> dict[str, int]:
    out = dict(stats)
    out[action.stat] = min(MAX_STAT, out[action.stat] + action.gain)
    return out


def mood(stats: dict[str, int]) -> str:
    """happy / ok / sad / sleepy — имена совпадают с папками assets/expressions."""
    avg = sum(stats[k] for k in STATS) / len(STATS)
    others = [stats[k] for k in STATS if k != "rest"]
    if stats["rest"] < 25 and sum(others) / len(others) >= 35:
        return "sleepy"  # не хватает именно сна, остальное в порядке
    if avg >= 60:
        return "happy"
    if avg >= 30:
        return "ok"
    return "sad"


def bar(value: int, width: int = 10) -> str:
    filled = round(value / MAX_STAT * width)
    return "▰" * filled + "▱" * (width - filled)
