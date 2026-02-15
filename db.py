"""
Database helper functions for IELTS Speaking App.
Shared between bot (app.py) and web server (web_server.py).
"""
import sqlite3
import json
from datetime import datetime, timedelta

DB_NAME = "bot.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def migrate():
    """Run all database migrations."""
    conn = get_connection()
    c = conn.cursor()

    # Existing tables (from app.py init_db)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        contact TEXT,
        tariff TEXT DEFAULT 'free',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        image_path TEXT,
        caption TEXT,
        schedule_time TIMESTAMP,
        sent INTEGER DEFAULT 0,
        FOREIGN KEY (admin_id) REFERENCES admins (user_id)
    )''')

    # Add new columns to users (safe: no error if already exists)
    for col, col_type, default in [
        ("first_name", "TEXT", "''"),
        ("username", "TEXT", "''"),
        ("photo_url", "TEXT", "''"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # New table: sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
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

    # New table: responses
    c.execute('''CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        question_text TEXT,
        transcription TEXT,
        duration INTEGER DEFAULT 0,
        part INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id)
    )''')

    # New table: daily_study
    c.execute('''CREATE TABLE IF NOT EXISTS daily_study (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        minutes INTEGER DEFAULT 0,
        sessions_count INTEGER DEFAULT 0,
        UNIQUE(user_id, date),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')

    # New table: user_settings
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        dark_mode INTEGER DEFAULT 0,
        notifications INTEGER DEFAULT 1,
        language TEXT DEFAULT 'en',
        daily_goal INTEGER DEFAULT 30,
        target_score REAL DEFAULT 6.5,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')

    # Add target_score column if not exists
    try:
        c.execute("ALTER TABLE user_settings ADD COLUMN target_score REAL DEFAULT 6.5")
    except sqlite3.OperationalError:
        pass

    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attempts_attempt_time ON attempts(attempt_time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_responses_session_id ON responses(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_daily_study_user_date ON daily_study(user_id, date)")

    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (5471121432,))

    conn.commit()
    conn.close()


# ─── User helpers ──────────────────────────────────────────────

def get_or_create_user(user_id, first_name="", username="", photo_url=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute(
            "INSERT INTO users (user_id, first_name, username, photo_url) VALUES (?, ?, ?, ?)",
            (user_id, first_name, username, photo_url)
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    else:
        # Update profile info
        c.execute(
            "UPDATE users SET first_name=?, username=?, photo_url=? WHERE user_id=?",
            (first_name or user["first_name"], username or user["username"],
             photo_url or user["photo_url"], user_id)
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return dict(user)


def get_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None


# ─── Settings helpers ──────────────────────────────────────────

def get_user_settings(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    settings = c.fetchone()
    if not settings:
        c.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
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
    # Ensure row exists
    c.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,))
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [user_id]
    c.execute(f"UPDATE user_settings SET {set_clause} WHERE user_id=?", values)
    conn.commit()
    conn.close()


# ─── Session helpers ───────────────────────────────────────────

def create_session(user_id, session_type="practice", part=1):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (user_id, type, part, status) VALUES (?, ?, ?, 'active')",
        (user_id, session_type, part)
    )
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    session = c.fetchone()
    conn.close()
    return dict(session) if session else None


def add_response(session_id, question_text, transcription, duration, part):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO responses (session_id, question_text, transcription, duration, part) VALUES (?, ?, ?, ?, ?)",
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
            score_fluency=?, score_lexical=?, score_grammar=?,
            score_pronunciation=?, score_overall=?,
            feedback=?, completed_at=?
        WHERE id=?""",
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
                start_dt = datetime.fromisoformat(started)
                minutes = max(1, int((datetime.utcnow() - start_dt).total_seconds() / 60))
            except (ValueError, TypeError):
                minutes = 1
        else:
            minutes = 1

        c.execute(
            """INSERT INTO daily_study (user_id, date, minutes, sessions_count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(user_id, date)
               DO UPDATE SET minutes = minutes + ?, sessions_count = sessions_count + 1""",
            (user_id, today, minutes, minutes)
        )

    conn.commit()
    conn.close()


def get_session_responses(session_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM responses WHERE session_id = ? ORDER BY id", (session_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Progress helpers ──────────────────────────────────────────

def get_weekly_progress(user_id):
    """Get study data for the last 7 days."""
    conn = get_connection()
    c = conn.cursor()
    days = []
    for i in range(6, -1, -1):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        c.execute(
            "SELECT minutes, sessions_count FROM daily_study WHERE user_id=? AND date=?",
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
    c = conn.cursor()
    streak = 0
    day = datetime.utcnow()
    # Check if today has study
    today_str = day.strftime("%Y-%m-%d")
    c.execute("SELECT 1 FROM daily_study WHERE user_id=? AND date=? AND minutes > 0", (user_id, today_str))
    if not c.fetchone():
        # Check yesterday as start
        day = day - timedelta(days=1)
        yesterday_str = day.strftime("%Y-%m-%d")
        c.execute("SELECT 1 FROM daily_study WHERE user_id=? AND date=? AND minutes > 0", (user_id, yesterday_str))
        if not c.fetchone():
            conn.close()
            return 0

    while True:
        date_str = day.strftime("%Y-%m-%d")
        c.execute("SELECT 1 FROM daily_study WHERE user_id=? AND date=? AND minutes > 0", (user_id, date_str))
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
        "SELECT * FROM sessions WHERE user_id=? AND status='completed' ORDER BY completed_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions(user_id, limit=50):
    """Get all completed sessions for history."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM sessions WHERE user_id=? AND status='completed' ORDER BY completed_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_detail(session_id):
    """Get session with all responses."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    session = c.fetchone()
    if not session:
        conn.close()
        return None
    c.execute("SELECT * FROM responses WHERE session_id = ? ORDER BY id", (session_id,))
    responses = c.fetchall()
    conn.close()
    result = dict(session)
    result["responses"] = [dict(r) for r in responses]
    return result


def get_total_sessions(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM sessions WHERE user_id=? AND status='completed'", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0


def get_daily_sessions_count(user_id):
    """Get number of sessions started today."""
    conn = get_connection()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute(
        "SELECT sessions_count FROM daily_study WHERE user_id=? AND date=?",
        (user_id, today)
    )
    row = c.fetchone()
    conn.close()
    return row["sessions_count"] if row else 0


def get_average_score(user_id, limit=10):
    """Get average overall score from recent completed sessions."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT AVG(score_overall) as avg_score FROM (SELECT score_overall FROM sessions WHERE user_id=? AND status='completed' AND score_overall IS NOT NULL ORDER BY completed_at DESC LIMIT ?)",
        (user_id, limit)
    )
    row = c.fetchone()
    conn.close()
    return round(row["avg_score"], 1) if row and row["avg_score"] else None


def get_total_practice_hours(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(minutes), 0) as total FROM daily_study WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    total_minutes = row["total"] if row else 0
    return round(total_minutes / 60, 1)
