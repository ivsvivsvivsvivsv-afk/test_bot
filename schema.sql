-- ============================================================
-- HYDRA BOT — PostgreSQL Schema (v7.3 Production MVP)
-- ============================================================
-- Запускается ОДИН РАЗ при первичной настройке:
--   psql -U hydra -d hydra_bot -f schema.sql
--
-- Безопасно запускать повторно: все объекты используют
-- IF NOT EXISTS / OR REPLACE / ON CONFLICT DO NOTHING.
-- ============================================================

BEGIN;

-- ============================================
-- ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id          BIGINT PRIMARY KEY,              -- Telegram ID
    username         VARCHAR(255),                     -- @username
    first_name       VARCHAR(255),                     -- Имя в Telegram

    -- Состояние квеста (FSM хранится в Redis, здесь — персистентный бэкап)
    quest_state      VARCHAR(50) DEFAULT 'start',
    quest_completed  BOOLEAN     DEFAULT FALSE,

    -- Выборы игрока
    player_class     VARCHAR(20),                      -- businessman / creator / analyst / manager
    weapon           VARCHAR(20),                      -- marketing / analytics / copywriting / design / management / video

    -- Результаты
    score            INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 3),
    round_number     INTEGER DEFAULT 0 CHECK (round_number >= 0 AND round_number <= 3),
    current_statement_hash VARCHAR(64),                -- SHA256 утверждения
    current_is_truth BOOLEAN,

    -- Контакты (НИКОГДА НЕ УДАЛЯЮТСЯ при сбросе прогресса)
    phone            VARCHAR(20),
    email            VARCHAR(255),
    workshop_registered BOOLEAN DEFAULT FALSE,

    -- Арена (хакатон)
    arena_registered BOOLEAN DEFAULT FALSE,
    arena_q1_experience VARCHAR(50),          -- beginner / intermediate / advanced
    arena_q2_tools      VARCHAR(50),          -- chat / image / dev / all
    arena_q3_goal       VARCHAR(50),          -- bot / analytics / content / custom

    -- Дожим
    -- last_activity НЕ хранится здесь! Только Redis SETEX activity:{user_id} TTL
    followup_stage     INTEGER DEFAULT 0 CHECK (followup_stage >= -1 AND followup_stage <= 5),
    followup_completed BOOLEAN DEFAULT FALSE,

    -- Блокировка бота
    is_blocked       BOOLEAN DEFAULT FALSE,

    -- Upsell
    upsell_shown     BOOLEAN DEFAULT FALSE,

    -- Метаданные
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    quest_completed_at TIMESTAMPTZ,              -- Когда квест завершён (для корректного дожима)

    -- Источник трафика
    utm_source       VARCHAR(100),                     -- Из deep link: /start utm_tiktok
    referrer         VARCHAR(255)
);

-- Индексы для частых запросов воронки и дожима
CREATE INDEX IF NOT EXISTS idx_users_quest_state
    ON users(quest_state);

CREATE INDEX IF NOT EXISTS idx_users_workshop
    ON users(workshop_registered);

CREATE INDEX IF NOT EXISTS idx_users_followup
    ON users(quest_completed, workshop_registered, followup_stage, is_blocked);

CREATE INDEX IF NOT EXISTS idx_users_blocked
    ON users(is_blocked) WHERE is_blocked = TRUE;

CREATE INDEX IF NOT EXISTS idx_users_created
    ON users(created_at);


-- ============================================
-- ТАБЛИЦА ПЛАТЕЖЕЙ
-- ============================================
CREATE TABLE IF NOT EXISTS payments (
    id                    SERIAL PRIMARY KEY,
    user_id               BIGINT NOT NULL REFERENCES users(user_id),

    yookassa_payment_id   VARCHAR(100) UNIQUE,
    amount                DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    currency              VARCHAR(3) DEFAULT 'RUB',

    status                VARCHAR(20) DEFAULT 'pending'
                          CHECK (status IN ('pending', 'succeeded', 'canceled', 'refunded')),
    description           TEXT,

    offer_type            VARCHAR(50) DEFAULT 'business_review',

    created_at            TIMESTAMPTZ DEFAULT NOW(),
    paid_at               TIMESTAMPTZ,

    metadata              JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_payments_user
    ON payments(user_id);

CREATE INDEX IF NOT EXISTS idx_payments_status
    ON payments(status);

CREATE INDEX IF NOT EXISTS idx_payments_yookassa
    ON payments(yookassa_payment_id);


-- ============================================
-- ТАБЛИЦА СОБЫТИЙ (АНАЛИТИКА)
-- ============================================
-- Нет FK на users: события могут логироваться до создания строки user
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    event_type  VARCHAR(50) NOT NULL,
    event_data  JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_user
    ON events(user_id);

CREATE INDEX IF NOT EXISTS idx_events_type
    ON events(event_type);

CREATE INDEX IF NOT EXISTS idx_events_created
    ON events(created_at);


-- ============================================
-- ТАБЛИЦА КОНФИГУРАЦИИ (горячая смена параметров)
-- ============================================
CREATE TABLE IF NOT EXISTS config (
    key        VARCHAR(100) PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO config (key, value) VALUES
    ('upsell_total_slots', '10'),
    ('upsell_price',       '5000'),
    ('upsell_enabled',     'true'),
    ('followup_enabled',   'true'),
    ('bot_active',         'true')
ON CONFLICT (key) DO NOTHING;


-- ============================================
-- PATCH 2: admin API / leads / notifications
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS idle_reminder_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS course_soon_sent BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    scheduled_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    result_sent INT,
    result_failed INT
);

CREATE TABLE IF NOT EXISTS notification_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    text_template TEXT NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    trigger_config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_notes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    admin_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_statuses (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    status VARCHAR(30) DEFAULT 'new',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by BIGINT
);

CREATE INDEX IF NOT EXISTS idx_lead_notes_user
    ON lead_notes(user_id);

CREATE INDEX IF NOT EXISTS idx_lead_statuses_status
    ON lead_statuses(status);

CREATE INDEX IF NOT EXISTS idx_events_type_created
    ON events(event_type, created_at);


-- ============================================
-- ТРИГГЕР auto-update updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- PG 14+ поддерживает CREATE OR REPLACE TRIGGER
DROP TRIGGER IF EXISTS users_updated_at ON users;
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS config_updated_at ON config;
CREATE TRIGGER config_updated_at
    BEFORE UPDATE ON config
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

COMMIT;
