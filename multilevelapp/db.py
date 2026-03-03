"""
Database helper functions for Multilevel Speaking Practice App.
Uses PostgreSQL via psycopg2 with a connection pool.
"""
import os
import json
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import psycopg2.pool

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL", "")
        _pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)
    return _pool


class _Conn:
    """Wraps a pooled psycopg2 connection. Returns it to pool on close()."""

    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return self._raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        _get_pool().putconn(self._raw)


def get_connection():
    return _Conn(_get_pool().getconn())


def _to_dt(val):
    """Coerce value to datetime (psycopg2 returns datetime, SQLite returns string)."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def migrate():
    """Create/update all tables. Uses autocommit so DDL never rolls back."""
    dsn = os.getenv("DATABASE_URL", "")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            contact TEXT,
            tariff TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            first_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            photo_url TEXT DEFAULT '',
            referral_code TEXT,
            bonus_mocks INTEGER DEFAULT 0,
            mock_total INTEGER DEFAULT 7,
            mock_used INTEGER DEFAULT 0,
            practice_total INTEGER DEFAULT 50,
            practice_used INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id BIGINT PRIMARY KEY
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(user_id),
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT REFERENCES admins(user_id),
            image_path TEXT,
            caption TEXT,
            schedule_time TIMESTAMP,
            sent INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            type TEXT NOT NULL DEFAULT 'practice',
            part TEXT DEFAULT '1.1',
            status TEXT DEFAULT 'active',
            score_fluency REAL,
            score_lexical REAL,
            score_grammar REAL,
            score_pronunciation REAL,
            score_overall REAL,
            feedback TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            question_text TEXT,
            transcription TEXT,
            duration INTEGER DEFAULT 0,
            part TEXT DEFAULT '1',
            debate_side TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_study (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            date TEXT NOT NULL,
            minutes INTEGER DEFAULT 0,
            sessions_count INTEGER DEFAULT 0,
            UNIQUE(user_id, date)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
            dark_mode INTEGER DEFAULT 0,
            notifications INTEGER DEFAULT 1,
            language TEXT DEFAULT 'en',
            daily_goal INTEGER DEFAULT 30,
            target_score REAL DEFAULT 6.5,
            target_level TEXT DEFAULT 'B2'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            referrer_id BIGINT NOT NULL REFERENCES users(user_id),
            referred_id BIGINT NOT NULL REFERENCES users(user_id),
            rewarded INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id),
            plan TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            expires_at TIMESTAMP,
            mock_limit INTEGER DEFAULT 0,
            practice_limit INTEGER DEFAULT 0,
            mock_used INTEGER DEFAULT 0,
            practice_used INTEGER DEFAULT 0,
            amount INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_by BIGINT
        )
    """)

    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attempts_attempt_time ON attempts(attempt_time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_responses_session_id ON responses(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_daily_study_user_date ON daily_study(user_id, date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)")
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
    except Exception:
        pass

    # Seed admin
    c.execute("INSERT INTO admins (user_id) VALUES (5471121432) ON CONFLICT DO NOTHING")

    conn.close()


def score_to_cefr(score):
    """Convert 0-75 score to CEFR level."""
    if score is None:
        return None
    score = int(score)
    if score >= 65:
        return "C1"
    elif score >= 51:
        return "B2"
    elif score >= 38:
        return "B1"
    else:
        return "Below B1"


# ─── User helpers ──────────────────────────────────────────────

def get_or_create_user(user_id, first_name="", username="", photo_url=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute(
            "INSERT INTO users (user_id, first_name, username, photo_url) VALUES (%s, %s, %s, %s)",
            (user_id, first_name, username, photo_url)
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
    else:
        c.execute(
            "UPDATE users SET first_name=%s, username=%s, photo_url=%s WHERE user_id=%s",
            (first_name or user["first_name"], username or user["username"],
             photo_url or user["photo_url"], user_id)
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = c.fetchone()
    conn.close()
    return dict(user)


def get_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None


# ─── Settings helpers ──────────────────────────────────────────

def get_user_settings(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    settings = c.fetchone()
    if not settings:
        c.execute("INSERT INTO user_settings (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
        settings = c.fetchone()
        conn.close()
        return dict(settings)
    conn.close()
    return dict(settings)


def update_user_settings(user_id, **kwargs):
    allowed = {"dark_mode", "notifications", "language", "daily_goal", "target_score", "target_level"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO user_settings (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    set_clause = ", ".join(f"{k}=%s" for k in fields)
    values = list(fields.values()) + [user_id]
    c.execute(f"UPDATE user_settings SET {set_clause} WHERE user_id=%s", values)
    conn.commit()
    conn.close()


# ─── Session helpers ───────────────────────────────────────────

def create_session(user_id, session_type="practice", part="1.1"):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (user_id, type, part, status) VALUES (%s, %s, %s, 'active') RETURNING id",
        (user_id, session_type, part)
    )
    session_id = c.fetchone()["id"]
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = c.fetchone()
    conn.close()
    return dict(session) if session else None


def add_response(session_id, question_text, transcription, duration, part):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO responses (session_id, question_text, transcription, duration, part) "
        "VALUES (%s, %s, %s, %s, %s)",
        (session_id, question_text, transcription, duration, part)
    )
    conn.commit()
    conn.close()


def complete_session(session_id, scores, feedback):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.utcnow()
    c.execute(
        """UPDATE sessions SET
            status='completed',
            score_fluency=%s, score_lexical=%s, score_grammar=%s,
            score_pronunciation=%s, score_overall=%s,
            feedback=%s, completed_at=%s
        WHERE id=%s""",
        (
            scores.get("fluency"), scores.get("lexical"),
            scores.get("grammar"), scores.get("pronunciation"),
            scores.get("overall"), feedback, now, session_id
        )
    )

    # Update daily_study
    c.execute("SELECT user_id, started_at FROM sessions WHERE id = %s", (session_id,))
    row = c.fetchone()
    if row:
        today = now.strftime("%Y-%m-%d")
        user_id = row["user_id"]
        started = _to_dt(row["started_at"])
        if started:
            minutes = max(1, int((now - started).total_seconds() / 60))
        else:
            minutes = 1

        c.execute(
            """INSERT INTO daily_study (user_id, date, minutes, sessions_count)
               VALUES (%s, %s, %s, 1)
               ON CONFLICT(user_id, date)
               DO UPDATE SET
                   minutes = daily_study.minutes + %s,
                   sessions_count = daily_study.sessions_count + 1""",
            (user_id, today, minutes, minutes)
        )

    conn.commit()
    conn.close()


def get_session_responses(session_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM responses WHERE session_id = %s ORDER BY id", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Progress helpers ──────────────────────────────────────────

def get_weekly_progress(user_id):
    """Get study data for the last 7 days (single query)."""
    conn = get_connection()
    c = conn.cursor()
    date_list = [(datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    c.execute(
        "SELECT date, minutes, sessions_count FROM daily_study "
        "WHERE user_id=%s AND date = ANY(%s)",
        (user_id, date_list)
    )
    rows = {row["date"]: row for row in c.fetchall()}
    conn.close()
    return [
        {
            "date": d,
            "minutes": rows[d]["minutes"] if d in rows else 0,
            "sessions": rows[d]["sessions_count"] if d in rows else 0,
        }
        for d in date_list
    ]


def get_study_streak(user_id):
    """Calculate consecutive days of study ending today or yesterday."""
    conn = get_connection()
    c = conn.cursor()
    streak = 0
    day = datetime.utcnow()
    today_str = day.strftime("%Y-%m-%d")
    c.execute("SELECT 1 FROM daily_study WHERE user_id=%s AND date=%s AND minutes > 0", (user_id, today_str))
    if not c.fetchone():
        day = day - timedelta(days=1)
        yesterday_str = day.strftime("%Y-%m-%d")
        c.execute("SELECT 1 FROM daily_study WHERE user_id=%s AND date=%s AND minutes > 0", (user_id, yesterday_str))
        if not c.fetchone():
            conn.close()
            return 0

    while True:
        date_str = day.strftime("%Y-%m-%d")
        c.execute("SELECT 1 FROM daily_study WHERE user_id=%s AND date=%s AND minutes > 0", (user_id, date_str))
        if c.fetchone():
            streak += 1
            day -= timedelta(days=1)
        else:
            break
    conn.close()
    return streak


def get_recent_sessions(user_id, limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM sessions WHERE user_id=%s AND status='completed' ORDER BY completed_at DESC LIMIT %s",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions(user_id, limit=50):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM sessions WHERE user_id=%s AND status='completed' ORDER BY completed_at DESC LIMIT %s",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_detail(session_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = c.fetchone()
    if not session:
        conn.close()
        return None
    c.execute("SELECT * FROM responses WHERE session_id = %s ORDER BY id", (session_id,))
    responses = c.fetchall()
    conn.close()
    result = dict(session)
    result["responses"] = [dict(r) for r in responses]
    return result


def get_total_sessions(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM sessions WHERE user_id=%s AND status='completed'", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_daily_sessions_count(user_id):
    conn = get_connection()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute("SELECT sessions_count FROM daily_study WHERE user_id=%s AND date=%s", (user_id, today))
    row = c.fetchone()
    conn.close()
    return row["sessions_count"] if row else 0


def get_daily_mock_count(user_id):
    conn = get_connection()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute(
        "SELECT COUNT(*) as cnt FROM sessions WHERE user_id=%s AND type='mock' AND started_at::date = %s::date",
        (user_id, today)
    )
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_average_score(user_id, limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT AVG(score_overall) as avg_score FROM ("
        "  SELECT score_overall FROM sessions "
        "  WHERE user_id=%s AND status='completed' AND score_overall IS NOT NULL "
        "  ORDER BY completed_at DESC LIMIT %s"
        ") sub",
        (user_id, limit)
    )
    row = c.fetchone()
    conn.close()
    return round(row["avg_score"], 1) if row and row["avg_score"] else None


def get_total_practice_hours(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(minutes), 0) as total FROM daily_study WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    total_minutes = row["total"] if row else 0
    return round(total_minutes / 60, 1)


# ─── Leaderboard helpers ─────────────────────────────────────

def get_leaderboard(limit=20, min_sessions=3):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id, u.first_name, u.username,
               COUNT(s.id) as sessions,
               ROUND(AVG(s.score_overall)::numeric, 1) as avg_score
        FROM users u
        JOIN sessions s ON s.user_id = u.user_id
        WHERE s.status = 'completed' AND s.score_overall IS NOT NULL
        GROUP BY u.user_id, u.first_name, u.username
        HAVING COUNT(s.id) >= %s
        ORDER BY avg_score DESC
        LIMIT %s
    """, (min_sessions, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_rank(user_id, min_sessions=3):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, avg_score, sessions FROM (
            SELECT u.user_id,
                   ROUND(AVG(s.score_overall)::numeric, 1) as avg_score,
                   COUNT(s.id) as sessions
            FROM users u
            JOIN sessions s ON s.user_id = u.user_id
            WHERE s.status = 'completed' AND s.score_overall IS NOT NULL
            GROUP BY u.user_id
            HAVING COUNT(s.id) >= %s
        ) ranked
        ORDER BY avg_score DESC
    """, (min_sessions,))
    rows = c.fetchall()
    conn.close()
    for i, r in enumerate(rows):
        if r["user_id"] == user_id:
            return {"rank": i + 1, "avg_score": r["avg_score"], "sessions": r["sessions"]}
    return None


# ─── Admin helpers ────────────────────────────────────────────

def is_admin(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = %s", (user_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)


def get_admin_stats():
    conn = get_connection()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    c.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(DISTINCT user_id) as cnt FROM sessions WHERE started_at::date = %s::date", (today,))
    active_today = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM sessions WHERE started_at::date = %s::date", (today,))
    sessions_today = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM users WHERE tariff != 'free'")
    premium_count = c.fetchone()["cnt"]

    conn.close()
    return {
        "total_users": total_users,
        "active_today": active_today,
        "sessions_today": sessions_today,
        "premium_count": premium_count,
    }


def search_users(query, limit=20):
    conn = get_connection()
    c = conn.cursor()
    like = f"%{query}%"
    c.execute("""
        SELECT u.user_id, u.first_name, u.username, u.tariff, u.created_at,
               COUNT(s.id) as sessions
        FROM users u
        LEFT JOIN sessions s ON s.user_id = u.user_id AND s.status = 'completed'
        WHERE u.first_name ILIKE %s OR u.username ILIKE %s OR CAST(u.user_id AS TEXT) LIKE %s
        GROUP BY u.user_id, u.first_name, u.username, u.tariff, u.created_at
        ORDER BY u.created_at DESC
        LIMIT %s
    """, (like, like, like, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_tariff(user_id, tariff):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET tariff = %s WHERE user_id = %s", (tariff, user_id))
    conn.commit()
    conn.close()


# ─── Referral helpers ─────────────────────────────────────────

# migrate_referrals and migrate_subscriptions are merged into migrate()

def generate_referral_code(user_id):
    """Generate unique 8-char referral code for user."""
    import string
    import random as rnd

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT referral_code FROM users WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    if row and row["referral_code"]:
        conn.close()
        return row["referral_code"]

    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = ''.join(rnd.choices(chars, k=8))
        c.execute("SELECT 1 FROM users WHERE referral_code = %s", (code,))
        if not c.fetchone():
            c.execute("UPDATE users SET referral_code = %s WHERE user_id = %s", (code, user_id))
            conn.commit()
            conn.close()
            return code

    conn.close()
    return None


def process_referral(referred_id, code):
    """Apply referral code: both users get +1 bonus mock."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT user_id FROM users WHERE referral_code = %s", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": "Invalid referral code"}

    referrer_id = row["user_id"]
    if referrer_id == referred_id:
        conn.close()
        return {"error": "Cannot use your own code"}

    c.execute("SELECT 1 FROM referrals WHERE referred_id = %s", (referred_id,))
    if c.fetchone():
        conn.close()
        return {"error": "You have already used a referral code"}

    c.execute("INSERT INTO referrals (referrer_id, referred_id, rewarded) VALUES (%s, %s, 1)",
              (referrer_id, referred_id))
    c.execute("UPDATE users SET bonus_mocks = COALESCE(bonus_mocks, 0) + 1 WHERE user_id = %s", (referrer_id,))
    c.execute("UPDATE users SET bonus_mocks = COALESCE(bonus_mocks, 0) + 1 WHERE user_id = %s", (referred_id,))

    conn.commit()
    conn.close()
    return {"success": True}


def get_referral_stats(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT referral_code, COALESCE(bonus_mocks, 0) as bonus_mocks FROM users WHERE user_id = %s", (user_id,))
    user = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = %s", (user_id,))
    count = c.fetchone()["cnt"]
    conn.close()
    return {
        "referral_code": user["referral_code"] if user else None,
        "bonus_mocks": user["bonus_mocks"] if user else 0,
        "referral_count": count,
    }


def use_bonus_mock(user_id):
    """Use one bonus mock. Returns True if bonus was used."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(bonus_mocks, 0) as bonus FROM users WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    if row and row["bonus"] > 0:
        c.execute("UPDATE users SET bonus_mocks = bonus_mocks - 1 WHERE user_id = %s", (user_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


# ─── Subscription helpers ─────────────────────────────────────

PLANS = {
    "weekly": {"mock_limit": 7, "practice_limit": 50, "amount": 7000, "days": 7},
    "monthly": {"mock_limit": 24, "practice_limit": 200, "amount": 20000, "days": 30},
}


def create_subscription_request(user_id, plan):
    if plan not in PLANS:
        return {"error": "Invalid plan"}

    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT id FROM subscriptions WHERE user_id = %s AND status = 'pending'", (user_id,))
    if c.fetchone():
        conn.close()
        return {"error": "You already have a pending request"}

    plan_info = PLANS[plan]
    c.execute(
        "INSERT INTO subscriptions (user_id, plan, status, mock_limit, practice_limit, amount) "
        "VALUES (%s, %s, 'pending', %s, %s, %s) RETURNING id",
        (user_id, plan, plan_info["mock_limit"], plan_info["practice_limit"], plan_info["amount"])
    )
    sub_id = c.fetchone()["id"]
    conn.commit()
    conn.close()
    return {"success": True, "subscription_id": sub_id}


def approve_subscription(sub_id, admin_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM subscriptions WHERE id = %s AND status = 'pending'", (sub_id,))
    sub = c.fetchone()
    if not sub:
        conn.close()
        return {"error": "Subscription not found or not pending"}

    sub = dict(sub)
    plan_info = PLANS.get(sub["plan"], {})
    days = plan_info.get("days", 7)

    now = datetime.utcnow()
    expires = now + timedelta(days=days)

    c.execute(
        "UPDATE subscriptions SET status='active', started_at=%s, expires_at=%s, "
        "approved_by=%s, mock_used=0, practice_used=0 WHERE id=%s",
        (now, expires, admin_id, sub_id)
    )
    c.execute("UPDATE users SET tariff = %s WHERE user_id = %s", (sub["plan"], sub["user_id"]))

    conn.commit()
    conn.close()
    return {"success": True, "user_id": sub["user_id"], "plan": sub["plan"],
            "expires_at": expires.isoformat()}


def reject_subscription(sub_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM subscriptions WHERE id = %s AND status = 'pending'", (sub_id,))
    sub = c.fetchone()
    if not sub:
        conn.close()
        return {"error": "Subscription not found or not pending"}

    sub = dict(sub)
    c.execute("UPDATE subscriptions SET status='cancelled' WHERE id=%s", (sub_id,))
    conn.commit()
    conn.close()
    return {"success": True, "user_id": sub["user_id"]}


def get_active_subscription(user_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "SELECT * FROM subscriptions WHERE user_id = %s AND status = 'active' ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    sub = c.fetchone()
    if not sub:
        conn.close()
        return None

    sub = dict(sub)

    expires = _to_dt(sub.get("expires_at"))
    if expires and datetime.utcnow() > expires:
        c.execute("UPDATE subscriptions SET status='expired' WHERE id=%s", (sub["id"],))
        c.execute("UPDATE users SET tariff='free' WHERE user_id=%s", (user_id,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return sub


def get_pending_subscription(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM subscriptions WHERE user_id = %s AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    sub = c.fetchone()
    conn.close()
    return dict(sub) if sub else None


def increment_mock_usage(user_id):
    sub = get_active_subscription(user_id)
    if sub:
        if sub["mock_used"] >= sub["mock_limit"]:
            return False
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE subscriptions SET mock_used = mock_used + 1 WHERE id = %s", (sub["id"],))
        conn.commit()
        conn.close()
        return True

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT mock_total, mock_used FROM users WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    if row["mock_used"] >= row["mock_total"]:
        conn.close()
        return use_bonus_mock(user_id)

    c.execute("UPDATE users SET mock_used = mock_used + 1 WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    return True


def increment_practice_usage(user_id):
    sub = get_active_subscription(user_id)
    if sub:
        if sub["practice_used"] >= sub["practice_limit"]:
            return False
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE subscriptions SET practice_used = practice_used + 1 WHERE id = %s", (sub["id"],))
        conn.commit()
        conn.close()
        return True

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT practice_total, practice_used FROM users WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    if row["practice_used"] >= row["practice_total"]:
        conn.close()
        return False

    c.execute("UPDATE users SET practice_used = practice_used + 1 WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    return True


def get_user_limits(user_id):
    """Return combined limit info (free or subscription). Uses single DB connection."""
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        "SELECT * FROM subscriptions WHERE user_id = %s AND status = 'active' ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    sub = c.fetchone()
    sub = dict(sub) if sub else None

    if sub:
        expires = _to_dt(sub.get("expires_at"))
        if expires and datetime.utcnow() > expires:
            expired_id = sub["id"]
            c.execute("UPDATE subscriptions SET status='expired' WHERE id=%s", (expired_id,))
            c.execute("UPDATE users SET tariff='free' WHERE user_id=%s", (user_id,))
            conn.commit()
            sub = None

    c.execute(
        "SELECT * FROM subscriptions WHERE user_id = %s AND status = 'pending' ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    pending_row = c.fetchone()
    pending = dict(pending_row) if pending_row else None

    c.execute(
        "SELECT COALESCE(bonus_mocks, 0) as bonus_mocks, mock_total, mock_used, "
        "practice_total, practice_used FROM users WHERE user_id = %s",
        (user_id,)
    )
    user_row = c.fetchone()
    conn.close()

    bonus_mocks = user_row["bonus_mocks"] if user_row else 0

    if sub:
        expires = _to_dt(sub.get("expires_at"))
        days_left = max(0, (expires - datetime.utcnow()).days) if expires else 0
        return {
            "plan": sub["plan"],
            "status": "active",
            "mock_used": sub["mock_used"],
            "mock_limit": sub["mock_limit"],
            "mock_remaining": max(0, sub["mock_limit"] - sub["mock_used"]) + bonus_mocks,
            "practice_used": sub["practice_used"],
            "practice_limit": sub["practice_limit"],
            "practice_remaining": max(0, sub["practice_limit"] - sub["practice_used"]),
            "bonus_mocks": bonus_mocks,
            "days_left": days_left,
            "expires_at": sub["expires_at"].isoformat() if isinstance(sub["expires_at"], datetime) else sub["expires_at"],
            "pending": None,
        }

    if not user_row:
        return {
            "plan": "free", "status": "free",
            "mock_used": 0, "mock_limit": 7, "mock_remaining": 7 + bonus_mocks,
            "practice_used": 0, "practice_limit": 50, "practice_remaining": 50,
            "bonus_mocks": bonus_mocks, "days_left": None, "expires_at": None,
            "pending": pending,
        }

    return {
        "plan": "free",
        "status": "free",
        "mock_used": user_row["mock_used"],
        "mock_limit": user_row["mock_total"],
        "mock_remaining": max(0, user_row["mock_total"] - user_row["mock_used"]) + bonus_mocks,
        "practice_used": user_row["practice_used"],
        "practice_limit": user_row["practice_total"],
        "practice_remaining": max(0, user_row["practice_total"] - user_row["practice_used"]),
        "bonus_mocks": bonus_mocks,
        "days_left": None,
        "expires_at": None,
        "pending": pending,
    }


def get_pending_subscriptions():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT s.*, u.first_name, u.username
        FROM subscriptions s
        JOIN users u ON u.user_id = s.user_id
        WHERE s.status = 'pending'
        ORDER BY s.created_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Legacy stubs so migrate() calls don't fail if called elsewhere
def migrate_referrals():
    pass


def migrate_subscriptions():
    pass
