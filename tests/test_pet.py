from datetime import datetime, timedelta, timezone

from bot import pet
from bot.handlers.onboarding import parse_ref, valid_name

FULL = {k: 100 for k in pet.STATS}


def test_decay_is_gradual_and_never_negative():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert pet.decay(FULL, t0, t0 + timedelta(hours=10)) == {k: 80 for k in pet.STATS}
    assert pet.decay(FULL, t0, t0 + timedelta(days=30)) == {k: 0 for k in pet.STATS}
    # часы «назад» не добавляют очков
    assert pet.decay(FULL, t0, t0 - timedelta(hours=5)) == FULL


def test_action_caps_at_max():
    s = pet.apply_action({**FULL, "hydration": 95}, pet.ACTIONS["water"])
    assert s["hydration"] == 100


def test_moods():
    assert pet.mood(FULL) == "happy"
    assert pet.mood({k: 45 for k in pet.STATS}) == "ok"
    assert pet.mood({k: 10 for k in pet.STATS}) == "sad"
    assert pet.mood({**FULL, "rest": 10}) == "sleepy"


def test_bar():
    assert pet.bar(0) == "▱" * 10
    assert pet.bar(100) == "▰" * 10
    assert pet.bar(50) == "▰" * 5 + "▱" * 5


def test_parse_ref():
    assert parse_ref("ref_123") == 123
    assert parse_ref("ref_") is None
    assert parse_ref("ref_12a") is None
    assert parse_ref(None) is None


def test_valid_name():
    assert valid_name("  Пушок   Второй ") == "Пушок Второй"
    assert valid_name("123") is None
    assert valid_name("а" * 21) is None
