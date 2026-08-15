-- 每日打卡：Supabase (PostgreSQL) 建表脚本
-- 用法：打开 Supabase 控制台 → SQL Editor → 粘贴本文件全部内容 → Run
-- 说明：应用启动时也会自动建表；如连接串无建表权限，可手动执行本脚本。

CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_disabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

CREATE TABLE IF NOT EXISTS invite_codes (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            code TEXT NOT NULL UNIQUE,
            created_by BIGINT,
            created_at TEXT NOT NULL,
            used_by BIGINT,
            used_at TEXT,
            expires_at TEXT
        );

CREATE TABLE IF NOT EXISTS habits (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value_label TEXT,
            reminder_time TEXT,
            reminder_enabled INTEGER NOT NULL DEFAULT 0,
            color TEXT NOT NULL DEFAULT '#4f8cff',
            sort_order INTEGER NOT NULL DEFAULT 0,
            last_reminder_date TEXT,
            created_at TEXT NOT NULL
        );

CREATE TABLE IF NOT EXISTS checkins (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            habit_id BIGINT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            value TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (user_id, habit_id, date)
        );

CREATE TABLE IF NOT EXISTS push_subscriptions (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

CREATE TABLE IF NOT EXISTS blood_pressure (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            measured_at TEXT NOT NULL,
            systolic INTEGER NOT NULL,
            diastolic INTEGER NOT NULL,
            pulse INTEGER,
            note TEXT,
            created_at TEXT NOT NULL
        );

CREATE TABLE IF NOT EXISTS metrics (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            date TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        );

CREATE TABLE IF NOT EXISTS analyses (
            id BIGSERIAL PRIMARY KEY NOT NULL,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_start TEXT,
            period_end TEXT,
            content TEXT NOT NULL,
            model TEXT,
            created_at TEXT NOT NULL
        );

CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id);

CREATE INDEX IF NOT EXISTS idx_checkins_user_date ON checkins(user_id, date);

CREATE INDEX IF NOT EXISTS idx_checkins_habit_date ON checkins(habit_id, date);

CREATE INDEX IF NOT EXISTS idx_bp_user_time ON blood_pressure(user_id, measured_at);

CREATE INDEX IF NOT EXISTS idx_metrics_user_date ON metrics(user_id, date);

CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id);
