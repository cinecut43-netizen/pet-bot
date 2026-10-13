"""Тесты с настоящим PostgreSQL. Запуск:
TEST_DATABASE_URL=postgresql://user@host/db pytest
Без переменной тесты пропускаются. ВНИМАНИЕ: таблицы в этой базе удаляются."""

import os
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from bot.db import Database

DSN = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL не задан")

SLOTS = {"beanie": "head", "bow": "head", "scarf": "neck"}
MSK = timezone(timedelta(hours=3))


@pytest.fixture
async def db():
    conn = await asyncpg.connect(DSN)
    await conn.execute(
        "DROP TABLE IF EXISTS render_cache, events, care_log, owned_items, pets, users CASCADE")
    await conn.close()
    database = await Database.connect(DSN)
    yield database
    await database.close()


async def make_pet(db, uid=1, **kw):
    await db.upsert_user(uid, "u", "U")
    return await db.create_pet(uid, kw.get("name", "Пушок"), "cat", "gray", [], ["beanie", "bow", "scarf"])


async def test_upsert_and_referral(db):
    assert await db.upsert_user(1, "a", "A") is True
    assert await db.upsert_user(1, "a2", "A") is False
    await db.upsert_user(2, "b", "B", referred_by=1)
    await db.upsert_user(3, "c", "C", referred_by=999)  # неизвестный пригласивший
    await db.upsert_user(4, "d", "D", referred_by=4)    # сам себя
    rows = dict(await db.pool.fetch("SELECT id, referred_by FROM users"))
    assert rows == {1: None, 2: 1, 3: None, 4: None}


async def test_care_and_daily_limit(db):
    await make_pet(db)
    now = datetime(2026, 5, 1, 9, tzinfo=MSK)
    r = await db.care(1, "sleep", now=now)
    assert r.status == "ok" and r.pet.stats["rest"] == 100
    assert (await db.care(1, "sleep", now=now + timedelta(hours=1))).status == "limit"
    # на следующий день по Москве — снова можно
    assert (await db.care(1, "sleep", now=now + timedelta(days=1))).status == "ok"
    assert (await db.care(42, "water")).status == "no_pet"


async def test_after_reminder_flag(db):
    await make_pet(db)
    now = datetime(2026, 5, 1, 19, tzinfo=MSK)
    await db.mark_reminded(1, now)
    await db.care(1, "water", now=now + timedelta(hours=1))       # вскоре после напоминания
    await db.care(1, "read", now=now + timedelta(hours=4))        # уже сам
    await db.care(1, "move", from_reminder=True, now=now + timedelta(hours=4))
    flags = dict(await db.pool.fetch("SELECT action, after_reminder FROM care_log"))
    assert flags == {"water": True, "read": False, "move": True}


async def test_wardrobe_one_item_per_slot(db):
    await make_pet(db)
    assert await db.toggle_item(1, "beanie", SLOTS) == ["beanie"]
    assert await db.toggle_item(1, "scarf", SLOTS) == ["beanie", "scarf"]
    assert await db.toggle_item(1, "bow", SLOTS) == ["scarf", "bow"]   # бантик сменил шапку
    assert await db.toggle_item(1, "bow", SLOTS) == ["scarf"]          # снять
    assert await db.toggle_item(1, "glasses", SLOTS) is None           # не куплено


async def test_due_reminders(db):
    await make_pet(db, name="Рыжик")
    await db.pool.execute("UPDATE pets SET created_at = now() - interval '2 days'")
    evening = datetime.now(MSK).replace(hour=19, minute=30)
    morning = evening.replace(hour=10)
    assert await db.due_reminders(morning) == []
    assert await db.due_reminders(evening) == [(1, "Рыжик")]
    await db.mark_reminded(1, evening)
    assert await db.due_reminders(evening + timedelta(minutes=5)) == []


async def test_no_reminder_if_already_cared(db):
    await make_pet(db)
    await db.pool.execute("UPDATE pets SET created_at = now() - interval '2 days'")
    evening = datetime.now(MSK).replace(hour=19, minute=30)
    await db.care(1, "water", now=evening.replace(hour=12))
    assert await db.due_reminders(evening) == []


async def test_metrics_d7(db):
    for uid in (1, 2, 3):
        await make_pet(db, uid=uid)
    await db.pool.execute("UPDATE pets SET created_at = now() - interval '10 days'")
    d0 = await db.pool.fetchval("SELECT (created_at AT TIME ZONE 'Europe/Moscow')::date FROM pets LIMIT 1")
    await db.pool.execute(
        "INSERT INTO care_log (user_id, action, local_date, after_reminder) VALUES "
        "(1, 'water', $1, false), (2, 'water', $1, true), (3, 'water', $2, false)",
        d0 + timedelta(days=7), d0 + timedelta(days=6),
    )
    m = await db.metrics()
    assert (m["d7_cohort"], m["d7_self"], m["d7_any"]) == (3, 1, 2)


async def test_file_id_cache(db):
    assert await db.get_file_id("k") is None
    await db.save_file_id("k", "AAA")
    await db.save_file_id("k", "BBB")
    assert await db.get_file_id("k") == "BBB"
