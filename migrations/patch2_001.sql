-- ============================================================
-- HYDRA BOT — Patch 2 migrations
-- ============================================================
-- Запуск: psql -U hydra -d hydra_bot -f migrations/patch2_001.sql
-- Безопасно при повторном запуске (IF NOT EXISTS).
-- ============================================================

BEGIN;

-- Счётчик idle-напоминаний (для user_stuck после 3 напоминаний)
ALTER TABLE users ADD COLUMN IF NOT EXISTS idle_reminder_count INTEGER DEFAULT 0;

-- Дедупликация course_soon (не слать повторно)
ALTER TABLE users ADD COLUMN IF NOT EXISTS course_soon_sent BOOLEAN DEFAULT FALSE;

-- Индекс для воронки (stats по event_type + created_at)
CREATE INDEX IF NOT EXISTS idx_events_type_created ON events(event_type, created_at);

-- Рассылки из админки
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

-- Правила автоуведомлений
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

-- Лиды: заметки и статусы
CREATE TABLE IF NOT EXISTS lead_notes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    admin_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lead_notes_user ON lead_notes(user_id);

CREATE TABLE IF NOT EXISTS lead_statuses (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    status VARCHAR(30) DEFAULT 'new',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by BIGINT
);
CREATE INDEX IF NOT EXISTS idx_lead_statuses_status ON lead_statuses(status);

COMMIT;
