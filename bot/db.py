"""Работа с PostgreSQL через asyncpg."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

from . import pet as petlogic

SCHEMA = Path(__file__).with_name("schema.sql")
REMINDER_EFFECT_HOURS = 3  # дела в течение 3 ч после напоминания не считаем «самостоятельными»


@dataclass
class Pet:
    user_id: int
    name: str
    species: str
    color: str
    traits: list[str]
    equipped: list[str]
    stats: dict[str, int]
    created_at: datetime

    @property
    def mood(self) -> str:
        return petlogic.mood(self.stats)


@dataclass
class CareResult:
    status: str  # ok / limit / no_pet
    pet: Pet | None = None
    mood_before: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pet_from_row(row: asyncpg.Record, now: datetime) -> Pet:
    raw = {k: row[k] for k in petlogic.STATS}
    return Pet(
        user_id=row["user_id"],
        name=row["name"],
        species=row["species"],
        color=row["color"],
        traits=list(row["traits"]),
        equipped=list(row["equipped"]),
        stats=petlogic.decay(raw, row["stats_updated_at"], now),
        created_at=row["created_at"],
    )


class Database:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "Database":
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
        db = cls(pool)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA.read_text(encoding="utf-8"))
        return db

    async def close(self) -> None:
        await self.pool.close()

    # ---------- пользователи ----------

    async def upsert_user(self, user_id: int, username: str | None, first_name: str | None,
                          referred_by: int | None = None) -> bool:
        """Создаёт или обновляет пользователя. Возвращает True, если он новый.
        Пригласивший сохраняется только для новых и только если он сам есть в базе."""
        async with self.pool.acquire() as conn:
            if referred_by is not None and (
                referred_by == user_id
                or not await conn.fetchval("SELECT 1 FROM users WHERE id = $1", referred_by)
            ):
                referred_by = None
            row = await conn.fetchrow(
                """
                INSERT INTO users (id, username, first_name, referred_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        blocked = FALSE
                RETURNING (xmax = 0) AS inserted
                """,
                user_id, username, first_name, referred_by,
            )
            return bool(row["inserted"])

    async def set_reminder(self, user_id: int, *, enabled: bool | None = None,
                           hour: int | None = None) -> None:
        await self.pool.execute(
            """
            UPDATE users SET reminders_enabled = COALESCE($2, reminders_enabled),
                             reminder_hour = COALESCE($3, reminder_hour)
            WHERE id = $1
            """,
            user_id, enabled, hour,
        )

    async def get_reminder(self, user_id: int) -> tuple[bool, int]:
        row = await self.pool.fetchrow(
            "SELECT reminders_enabled, reminder_hour FROM users WHERE id = $1", user_id)
        return (row["reminders_enabled"], row["reminder_hour"]) if row else (False, 19)

    # ---------- питомец ----------

    async def get_pet(self, user_id: int) -> Pet | None:
        row = await self.pool.fetchrow("SELECT * FROM pets WHERE user_id = $1", user_id)
        return _pet_from_row(row, _now()) if row else None

    async def create_pet(self, user_id: int, name: str, species: str, color: str,
                         traits: list[str], starter_items: list[str]) -> Pet:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute(
                """
                INSERT INTO pets (user_id, name, species, color, traits)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id, name, species, color, traits,
            )
            await conn.executemany(
                "INSERT INTO owned_items (user_id, item_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [(user_id, item) for item in starter_items],
            )
        pet = await self.get_pet(user_id)
        assert pet is not None
        return pet

    async def care(self, user_id: int, action_key: str, from_reminder: bool = False,
                   now: datetime | None = None) -> CareResult:
        action = petlogic.ACTIONS[action_key]
        now = now or _now()
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT p.*, u.last_reminded_at,
                       (($2::timestamptz) AT TIME ZONE u.tz)::date AS local_today
                FROM pets p JOIN users u ON u.id = p.user_id
                WHERE p.user_id = $1
                FOR UPDATE OF p
                """,
                user_id, now,
            )
            if row is None:
                return CareResult("no_pet")
            pet = _pet_from_row(row, now)
            before = pet.mood
            done_today = await conn.fetchval(
                "SELECT count(*) FROM care_log WHERE user_id = $1 AND action = $2 AND local_date = $3",
                user_id, action.key, row["local_today"],
            )
            if done_today >= action.daily_limit:
                return CareResult("limit", pet, before)

            pet.stats = petlogic.apply_action(pet.stats, action)
            await conn.execute(
                """
                UPDATE pets SET hydration = $2, energy = $3, mind = $4, rest = $5,
                                stats_updated_at = $6
                WHERE user_id = $1
                """,
                user_id, *(pet.stats[k] for k in petlogic.STATS), now,
            )
            reminded = row["last_reminded_at"]
            after_reminder = from_reminder or (
                reminded is not None and (now - reminded).total_seconds() < REMINDER_EFFECT_HOURS * 3600
            )
            await conn.execute(
                """
                INSERT INTO care_log (user_id, action, local_date, after_reminder, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, action.key, row["local_today"], after_reminder, now,
            )
            return CareResult("ok", pet, before)

    # ---------- гардероб ----------

    async def owned_items(self, user_id: int) -> list[str]:
        rows = await self.pool.fetch(
            "SELECT item_id FROM owned_items WHERE user_id = $1 ORDER BY acquired_at, item_id", user_id)
        return [r["item_id"] for r in rows]

    async def toggle_item(self, user_id: int, item_id: str, slots: dict[str, str]) -> list[str] | None:
        """Надевает/снимает вещь. В одном слоте — одна вещь. None, если вещи нет у пользователя."""
        async with self.pool.acquire() as conn, conn.transaction():
            if not await conn.fetchval(
                "SELECT 1 FROM owned_items WHERE user_id = $1 AND item_id = $2", user_id, item_id):
                return None
            equipped = await conn.fetchval(
                "SELECT equipped FROM pets WHERE user_id = $1 FOR UPDATE", user_id)
            if equipped is None:
                return None
            equipped = list(equipped)
            if item_id in equipped:
                equipped.remove(item_id)
            else:
                slot = slots[item_id]
                equipped = [i for i in equipped if slots.get(i) != slot] + [item_id]
            await conn.execute("UPDATE pets SET equipped = $2 WHERE user_id = $1", user_id, equipped)
            return equipped

    # ---------- напоминания ----------

    async def due_reminders(self, now: datetime | None = None) -> list[tuple[int, str]]:
        """Кому пора напомнить: наступил выбранный час по местному времени,
        сегодня ещё не напоминали и сегодня ещё не было ни одного дела."""
        rows = await self.pool.fetch(
            """
            SELECT u.id, p.name
            FROM users u JOIN pets p ON p.user_id = u.id
            WHERE u.reminders_enabled AND NOT u.blocked
              AND extract(hour FROM ($1::timestamptz AT TIME ZONE u.tz))
                  BETWEEN u.reminder_hour AND u.reminder_hour + 2  -- догоняем, если бот лежал
              AND (u.last_reminded_at IS NULL
                   OR (u.last_reminded_at AT TIME ZONE u.tz)::date < ($1::timestamptz AT TIME ZONE u.tz)::date)
              AND (p.created_at AT TIME ZONE u.tz)::date < ($1::timestamptz AT TIME ZONE u.tz)::date
              AND NOT EXISTS (
                  SELECT 1 FROM care_log c
                  WHERE c.user_id = u.id
                    AND c.local_date = ($1::timestamptz AT TIME ZONE u.tz)::date)
            LIMIT 500
            """,
            now or _now(),
        )
        return [(r["id"], r["name"]) for r in rows]

    async def mark_reminded(self, user_id: int, now: datetime | None = None) -> None:
        await self.pool.execute(
            "UPDATE users SET last_reminded_at = $2 WHERE id = $1", user_id, now or _now())

    async def mark_blocked(self, user_id: int) -> None:
        await self.pool.execute("UPDATE users SET blocked = TRUE WHERE id = $1", user_id)

    # ---------- кэш картинок ----------

    async def get_file_id(self, key: str) -> str | None:
        return await self.pool.fetchval("SELECT file_id FROM render_cache WHERE key = $1", key)

    async def save_file_id(self, key: str, file_id: str) -> None:
        await self.pool.execute(
            "INSERT INTO render_cache (key, file_id) VALUES ($1, $2) "
            "ON CONFLICT (key) DO UPDATE SET file_id = EXCLUDED.file_id",
            key, file_id,
        )

    # ---------- аналитика ----------

    async def log_event(self, user_id: int | None, kind: str, **payload) -> None:
        await self.pool.execute(
            "INSERT INTO events (user_id, kind, payload) VALUES ($1, $2, $3::jsonb)",
            user_id, kind, json.dumps(payload, ensure_ascii=False),
        )

    async def metrics(self) -> dict:
        """Главные цифры из концепции.
        d7_self — доля тех, у кого 7-й день уже закончился и кто в этот день сам
        (не из напоминания и не в течение 3 ч после него) отметил хотя бы одно дело."""
        return dict(await self.pool.fetchrow(
            """
            WITH cohort AS (
                SELECT u.id, u.tz, (p.created_at AT TIME ZONE u.tz)::date AS d0
                FROM users u JOIN pets p ON p.user_id = u.id
            ),
            ripe AS (
                SELECT * FROM cohort WHERE (now() AT TIME ZONE tz)::date > d0 + 7
            )
            SELECT
                (SELECT count(*) FROM users)                                   AS users,
                (SELECT count(*) FROM pets)                                    AS pets,
                (SELECT count(DISTINCT user_id) FROM care_log
                  WHERE created_at > now() - interval '1 day')                 AS active_24h,
                (SELECT count(*) FROM users WHERE referred_by IS NOT NULL)     AS referred,
                (SELECT count(DISTINCT referred_by) FROM users
                  WHERE referred_by IS NOT NULL)                               AS inviters,
                (SELECT count(*) FROM ripe)                                    AS d7_cohort,
                (SELECT count(*) FROM ripe r WHERE EXISTS (
                    SELECT 1 FROM care_log c WHERE c.user_id = r.id
                      AND c.local_date = r.d0 + 7 AND NOT c.after_reminder))   AS d7_self,
                (SELECT count(*) FROM ripe r WHERE EXISTS (
                    SELECT 1 FROM care_log c WHERE c.user_id = r.id
                      AND c.local_date = r.d0 + 7))                            AS d7_any
            """
        ))
