"""
Database helper functions for IELTS Speaking App.
Shared between bot (app.py) and web server (web_server.py).
Uses PostgreSQL (Supabase) with connection pooling.
"""
import os
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:shahzod1602@db.tdraljrgkafpyiiiawyi.supabase.co:5432/postgres"
)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(2, 10, DATABASE_URL)
    return _pool


class PooledConnection:
    """Wrapper that returns connection to pool on close() instead of closing."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def close(self):
        self._pool.putconn(self._conn)

    def cursor(self, **kwargs):
        return self._conn.cursor(**kwargs)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    return PooledConnection(conn, pool)


def migrate():
    """Run all database migrations."""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        contact TEXT,
        tariff TEXT DEFAULT 'free',
        first_name TEXT DEFAULT '',
        username TEXT DEFAULT '',
        photo_url TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id BIGINT PRIMARY KEY
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS attempts (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ads (
        id SERIAL PRIMARY KEY,
        admin_id BIGINT,
        image_path TEXT,
        caption TEXT,
        schedule_time TIMESTAMP,
        sent INTEGER DEFAULT 0,
        FOREIGN KEY (admin_id) REFERENCES admins (user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        type TEXT NOT NULL DEFAULT 'practice',
        part INTEGER DEFAULT 1,
        status TEXT DEFAULT 'active',
        score_fluency REAL,
        score_lexical REAL,
        score_grammar REAL,
        score_pronunciation REAL,
        score_overall REAL,
        feedback TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS responses (
        id SERIAL PRIMARY KEY,
        session_id INTEGER NOT NULL,
        question_text TEXT,
        transcription TEXT,
        duration INTEGER DEFAULT 0,
        part INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS daily_study (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        date TEXT NOT NULL,
        minutes INTEGER DEFAULT 0,
        sessions_count INTEGER DEFAULT 0,
        UNIQUE(user_id, date),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        user_id BIGINT PRIMARY KEY,
        dark_mode INTEGER DEFAULT 0,
        notifications INTEGER DEFAULT 1,
        language TEXT DEFAULT 'en',
        daily_goal INTEGER DEFAULT 30,
        target_score REAL DEFAULT 6.5,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')

    conn.commit()

    # Add columns if they don't exist (each in its own transaction)
    for col, col_type, default in [
        ("first_name", "TEXT", "''"),
        ("username", "TEXT", "''"),
        ("photo_url", "TEXT", "''"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type} DEFAULT {default}")
            conn.commit()
        except Exception:
            conn.rollback()

    try:
        c.execute("ALTER TABLE user_settings ADD COLUMN target_score REAL DEFAULT 6.5")
        conn.commit()
    except Exception:
        conn.rollback()

    # Indexes (each in its own transaction to avoid cascade failures)
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_attempts_attempt_time ON attempts(attempt_time)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)",
        "CREATE INDEX IF NOT EXISTS idx_responses_session_id ON responses(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_daily_study_user_date ON daily_study(user_id, date)",
    ]:
        try:
            c.execute(idx_sql)
            conn.commit()
        except Exception:
            conn.rollback()

    c.execute("INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (5471121432,))
    conn.commit()
    conn.close()


# ─── User helpers ──────────────────────────────────────────────

def get_or_create_user(user_id, first_name="", username="", photo_url=""):
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
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
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None


# ─── Settings helpers ──────────────────────────────────────────

def get_user_settings(user_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    settings = c.fetchone()
    if not settings:
        c.execute("INSERT INTO user_settings (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
        settings = c.fetchone()
    conn.close()
    return dict(settings)


def update_user_settings(user_id, **kwargs):
    allowed = {"dark_mode", "notifications", "language", "daily_goal", "target_score"}
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

def create_session(user_id, session_type="practice", part=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (user_id, type, part, status) VALUES (%s, %s, %s, 'active') RETURNING id",
        (user_id, session_type, part)
    )
    session_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = c.fetchone()
    conn.close()
    return dict(session) if session else None


def add_response(session_id, question_text, transcription, duration, part):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO responses (session_id, question_text, transcription, duration, part) VALUES (%s, %s, %s, %s, %s)",
        (session_id, question_text, transcription, duration, part)
    )
    conn.commit()
    conn.close()


def complete_session(session_id, scores, feedback):
    conn = get_connection()
    c = conn.cursor()
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
            scores.get("overall"), feedback,
            datetime.utcnow().isoformat(), session_id
        )
    )

    # Update daily_study
    session = get_session(session_id)
    if session:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        user_id = session["user_id"]
        started = session["started_at"]
        if started:
            try:
                if isinstance(started, str):
                    start_dt = datetime.fromisoformat(started)
                else:
                    start_dt = started
                minutes = max(1, int((datetime.utcnow() - start_dt).total_seconds() / 60))
            except (ValueError, TypeError):
                minutes = 1
        else:
            minutes = 1

        c.execute(
            """INSERT INTO daily_study (user_id, date, minutes, sessions_count)
               VALUES (%s, %s, %s, 1)
               ON CONFLICT(user_id, date)
               DO UPDATE SET minutes = daily_study.minutes + %s, sessions_count = daily_study.sessions_count + 1""",
            (user_id, today, minutes, minutes)
        )

    conn.commit()
    conn.close()


def get_session_responses(session_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT * FROM responses WHERE session_id = %s ORDER BY id", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Progress helpers ──────────────────────────────────────────

def get_weekly_progress(user_id):
    """Get study data for the last 7 days."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    days = []
    for i in range(6, -1, -1):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        c.execute(
            "SELECT minutes, sessions_count FROM daily_study WHERE user_id=%s AND date=%s",
            (user_id, date)
        )
        row = c.fetchone()
        days.append({
            "date": date,
            "minutes": row["minutes"] if row else 0,
            "sessions": row["sessions_count"] if row else 0,
        })
    conn.close()
    return days


def get_study_streak(user_id):
    """Calculate consecutive days of study ending today or yesterday."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
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
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute(
        "SELECT * FROM sessions WHERE user_id=%s AND status='completed' ORDER BY completed_at DESC LIMIT %s",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions(user_id, limit=50):
    """Get all completed sessions for history."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute(
        "SELECT * FROM sessions WHERE user_id=%s AND status='completed' ORDER BY completed_at DESC LIMIT %s",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_detail(session_id):
    """Get session with all responses."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
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
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT COUNT(*) as cnt FROM sessions WHERE user_id=%s AND status='completed'", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_daily_sessions_count(user_id):
    """Get number of sessions started today."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute(
        "SELECT sessions_count FROM daily_study WHERE user_id=%s AND date=%s",
        (user_id, today)
    )
    row = c.fetchone()
    conn.close()
    return row["sessions_count"] if row else 0


def get_daily_mock_count(user_id):
    """Get number of mock sessions started today."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute(
        "SELECT COUNT(*) as cnt FROM sessions WHERE user_id=%s AND type='mock' AND started_at::date = %s::date",
        (user_id, today)
    )
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_average_score(user_id, limit=10):
    """Get average overall score from recent completed sessions."""
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute(
        "SELECT AVG(score_overall) as avg_score FROM (SELECT score_overall FROM sessions WHERE user_id=%s AND status='completed' AND score_overall IS NOT NULL ORDER BY completed_at DESC LIMIT %s) sub",
        (user_id, limit)
    )
    row = c.fetchone()
    conn.close()
    return round(row["avg_score"], 1) if row and row["avg_score"] else None


def get_total_practice_hours(user_id):
    conn = get_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT COALESCE(SUM(minutes), 0) as total FROM daily_study WHERE user_id=%s", (user_id,))
    row = c.fetchone()
    conn.close()
    total_minutes = row["total"] if row else 0
    return round(total_minutes / 60, 1)
