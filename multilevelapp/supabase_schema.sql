-- Supabase tables for Multilevel Speaking Practice backup
-- Run this in the Supabase SQL Editor (or via psql)

-- 1. Users (PK = user_id, same as Telegram user ID)
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    contact TEXT,
    tariff TEXT DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT now(),
    first_name TEXT DEFAULT '',
    username TEXT DEFAULT '',
    photo_url TEXT DEFAULT '',
    referral_code TEXT UNIQUE,
    bonus_mocks INTEGER DEFAULT 0
);

-- 2. Admins (PK = user_id)
CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY
);

-- 3. User settings (PK = user_id)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id BIGINT PRIMARY KEY,
    dark_mode INTEGER DEFAULT 0,
    notifications INTEGER DEFAULT 1,
    language TEXT DEFAULT 'en',
    daily_goal INTEGER DEFAULT 30,
    target_score REAL DEFAULT 6.5,
    target_level TEXT DEFAULT 'B2'
);

-- 4. Sessions (sqlite_id = UNIQUE reference to SQLite AUTOINCREMENT id)
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    sqlite_id BIGINT UNIQUE NOT NULL,
    user_id BIGINT NOT NULL,
    type TEXT DEFAULT 'practice',
    part TEXT DEFAULT '1.1',
    status TEXT DEFAULT 'active',
    score_fluency REAL,
    score_lexical REAL,
    score_grammar REAL,
    score_pronunciation REAL,
    score_overall REAL,
    feedback TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 5. Responses (sqlite_id = UNIQUE, session_sqlite_id references sessions.sqlite_id)
CREATE TABLE IF NOT EXISTS responses (
    id BIGSERIAL PRIMARY KEY,
    sqlite_id BIGINT UNIQUE NOT NULL,
    session_sqlite_id BIGINT,
    question_text TEXT,
    transcription TEXT,
    duration INTEGER DEFAULT 0,
    part TEXT DEFAULT '1',
    debate_side TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Attempts
CREATE TABLE IF NOT EXISTS attempts (
    id BIGSERIAL PRIMARY KEY,
    sqlite_id BIGINT UNIQUE,
    user_id BIGINT,
    attempt_time TIMESTAMPTZ DEFAULT now()
);

-- 7. Daily study
CREATE TABLE IF NOT EXISTS daily_study (
    id BIGSERIAL PRIMARY KEY,
    sqlite_id BIGINT UNIQUE NOT NULL,
    user_id BIGINT NOT NULL,
    date TEXT NOT NULL,
    minutes INTEGER DEFAULT 0,
    sessions_count INTEGER DEFAULT 0
);

-- 8. Referrals
CREATE TABLE IF NOT EXISTS referrals (
    id BIGSERIAL PRIMARY KEY,
    sqlite_id BIGINT UNIQUE NOT NULL,
    referrer_id BIGINT NOT NULL,
    referred_id BIGINT NOT NULL,
    rewarded INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 9. Ads
CREATE TABLE IF NOT EXISTS ads (
    id BIGSERIAL PRIMARY KEY,
    sqlite_id BIGINT UNIQUE,
    admin_id BIGINT,
    image_path TEXT,
    caption TEXT,
    schedule_time TIMESTAMPTZ,
    sent INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_sqlite_id ON sessions(sqlite_id);
CREATE INDEX IF NOT EXISTS idx_responses_session_sqlite_id ON responses(session_sqlite_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user_id ON attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_study_user_date ON daily_study(user_id, date);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
