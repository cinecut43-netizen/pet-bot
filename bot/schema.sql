-- Схема применяется при каждом старте бота (всё идемпотентно).

CREATE TABLE IF NOT EXISTS users (
    -- Храним минимум персональных данных (152-ФЗ): только Telegram id,
    -- без имени и username — для работы бота они не нужны.
    id                 BIGINT PRIMARY KEY,           -- Telegram user id
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    referred_by        BIGINT REFERENCES users(id) ON DELETE SET NULL,  -- кто пригласил (start=ref_ID)
    tz                 TEXT NOT NULL DEFAULT 'Europe/Moscow',
    reminder_hour      SMALLINT NOT NULL DEFAULT 19 CHECK (reminder_hour BETWEEN 0 AND 23),
    reminders_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    last_reminded_at   TIMESTAMPTZ,
    blocked            BOOLEAN NOT NULL DEFAULT FALSE  -- пользователь заблокировал бота
);

CREATE TABLE IF NOT EXISTS pets (
    user_id          BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    species          TEXT NOT NULL,
    color            TEXT NOT NULL,
    traits           TEXT[] NOT NULL DEFAULT '{}',
    equipped         TEXT[] NOT NULL DEFAULT '{}',
    hydration        SMALLINT NOT NULL DEFAULT 70,
    energy           SMALLINT NOT NULL DEFAULT 70,
    mind             SMALLINT NOT NULL DEFAULT 70,
    rest             SMALLINT NOT NULL DEFAULT 70,
    stats_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS owned_items (
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id     TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'starter',     -- starter / stars / gift
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);

-- Журнал дел — источник главной метрики (D7 без напоминания).
CREATE TABLE IF NOT EXISTS care_log (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action         TEXT NOT NULL,
    local_date     DATE NOT NULL,                -- дата в часовом поясе пользователя
    after_reminder BOOLEAN NOT NULL DEFAULT FALSE, -- нажато из напоминания или в течение 3 ч после него
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS care_log_user_date ON care_log (user_id, local_date);

-- Прочие события для аналитики: start, reminder_sent, позже inline_share и т.п.
CREATE TABLE IF NOT EXISTS events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,
    payload    JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_kind_time ON events (kind, created_at);

-- Telegram file_id для уже загруженных картинок: не грузим одно и то же дважды
-- (понадобится и для инлайн-режима на неделе 2).
CREATE TABLE IF NOT EXISTS render_cache (
    key        TEXT PRIMARY KEY,
    file_id    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
