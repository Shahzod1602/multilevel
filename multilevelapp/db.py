"""
Database helper functions for Multilevel Speaking Practice App.
Shared between bot (app.py) and web server (web_server.py).
"""
import sqlite3
import json
from datetime import datetime, timedelta

import supabase_sync as sb

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

    # Add target_level column if not exists (CEFR level, replaces target_score conceptually)
    try:
        c.execute("ALTER TABLE user_settings ADD COLUMN target_level TEXT DEFAULT 'B2'")
    except sqlite3.OperationalError:
        pass

    # Add debate_side column to responses (for Part 3 debate)
    try:
        c.execute("ALTER TABLE responses ADD COLUMN debate_side TEXT")
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

    # Run referral migrations
    migrate_referrals()


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
    result = dict(user)
    sb._fire_and_forget(sb.sync_user, user_id=user_id,
                        first_name=result.get("first_name", ""),
                        username=result.get("username", ""),
                        photo_url=result.get("photo_url", ""),
                        contact=result.get("contact"),
                        tariff=result.get("tariff", "free"),
                        referral_code=result.get("referral_code"),
                        bonus_mocks=result.get("bonus_mocks", 0),
                        created_at=result.get("created_at"))
    return result


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
    result = dict(settings)
    sb._fire_and_forget(sb.sync_user_settings, **result)
    return result


def update_user_settings(user_id, **kwargs):
    allowed = {"dark_mode", "notifications", "language", "daily_goal", "target_score", "target_level"}
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
    sb._fire_and_forget(sb.sync_user_settings, user_id=user_id, **fields)


# ─── Session helpers ───────────────────────────────────────────

def create_session(user_id, session_type="practice", part="1.1"):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (user_id, type, part, status) VALUES (?, ?, ?, 'active')",
        (user_id, session_type, part)
    )
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    sb._fire_and_forget(sb.sync_session_insert, sqlite_id=session_id,
                        user_id=user_id, session_type=session_type, part=part)
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
    response_id = c.lastrowid
    conn.commit()
    conn.close()
    sb._fire_and_forget(sb.sync_response_insert, sqlite_id=response_id,
                        session_sqlite_id=session_id,
                        question_text=question_text,
                        transcription=transcription,
                        duration=duration, part=part)


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

        # Sync daily_study to Supabase
        c.execute("SELECT id, minutes, sessions_count FROM daily_study WHERE user_id=? AND date=?",
                  (user_id, today))
        ds_row = c.fetchone()
        if ds_row:
            sb._fire_and_forget(sb.sync_daily_study, sqlite_id=ds_row["id"],
                                user_id=user_id, date=today,
                                minutes=ds_row["minutes"],
                                sessions_count=ds_row["sessions_count"])

    conn.commit()
    conn.close()
    sb._fire_and_forget(sb.sync_session_complete, sqlite_id=session_id,
                        scores=scores, feedback=feedback,
                        completed_at=datetime.utcnow().isoformat())


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


def get_daily_mock_count(user_id):
    """Get number of mock sessions started today."""
    conn = get_connection()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute(
        "SELECT COUNT(*) as cnt FROM sessions WHERE user_id=? AND type='mock' AND date(started_at)=?",
        (user_id, today)
    )
    row = c.fetchone()
    conn.close()
    return row["cnt"] if row else 0


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


# ─── Leaderboard helpers ─────────────────────────────────────

def get_leaderboard(limit=20, min_sessions=3):
    """Get top users by average overall score, requiring minimum sessions."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id, u.first_name, u.username,
               COUNT(s.id) as sessions,
               ROUND(AVG(s.score_overall), 1) as avg_score
        FROM users u
        JOIN sessions s ON s.user_id = u.user_id
        WHERE s.status = 'completed' AND s.score_overall IS NOT NULL
        GROUP BY u.user_id
        HAVING COUNT(s.id) >= ?
        ORDER BY avg_score DESC
        LIMIT ?
    """, (min_sessions, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_rank(user_id, min_sessions=3):
    """Get user's rank among all users with enough sessions."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, avg_score, sessions FROM (
            SELECT u.user_id,
                   ROUND(AVG(s.score_overall), 1) as avg_score,
                   COUNT(s.id) as sessions
            FROM users u
            JOIN sessions s ON s.user_id = u.user_id
            WHERE s.status = 'completed' AND s.score_overall IS NOT NULL
            GROUP BY u.user_id
            HAVING COUNT(s.id) >= ?
        )
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
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)


def get_admin_stats():
    conn = get_connection()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    c.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(DISTINCT user_id) as cnt FROM sessions WHERE date(started_at) = ?", (today,))
    active_today = c.fetchone()["cnt"]

    c.execute("SELECT COUNT(*) as cnt FROM sessions WHERE date(started_at) = ?", (today,))
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
        WHERE u.first_name LIKE ? OR u.username LIKE ? OR CAST(u.user_id AS TEXT) LIKE ?
        GROUP BY u.user_id
        ORDER BY u.created_at DESC
        LIMIT ?
    """, (like, like, like, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_tariff(user_id, tariff):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET tariff = ? WHERE user_id = ?", (tariff, user_id))
    conn.commit()
    conn.close()
    sb._fire_and_forget(sb.sync_user_tariff, user_id=user_id, tariff=tariff)


# ─── Referral helpers ─────────────────────────────────────────

def migrate_referrals():
    """Create referral tables and columns."""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER NOT NULL,
        referred_id INTEGER NOT NULL,
        rewarded INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES users (user_id),
        FOREIGN KEY (referred_id) REFERENCES users (user_id)
    )''')

    for col, col_type, default in [
        ("referral_code", "TEXT", "NULL"),
        ("bonus_mocks", "INTEGER", "0"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type} DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    c.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")

    conn.commit()
    conn.close()


def generate_referral_code(user_id):
    """Generate unique 8-char referral code for user."""
    import string
    import random as rnd

    conn = get_connection()
    c = conn.cursor()

    # Check if already has code
    c.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row["referral_code"]:
        conn.close()
        return row["referral_code"]

    # Generate unique code
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = ''.join(rnd.choices(chars, k=8))
        c.execute("SELECT 1 FROM users WHERE referral_code = ?", (code,))
        if not c.fetchone():
            c.execute("UPDATE users SET referral_code = ? WHERE user_id = ?", (code, user_id))
            conn.commit()
            conn.close()
            sb._fire_and_forget(sb.sync_user_field, user_id=user_id,
                                referral_code=code)
            return code

    conn.close()
    return None


def process_referral(referred_id, code):
    """Apply referral code: both users get +1 bonus mock."""
    conn = get_connection()
    c = conn.cursor()

    # Find referrer
    c.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"error": "Invalid referral code"}

    referrer_id = row["user_id"]
    if referrer_id == referred_id:
        conn.close()
        return {"error": "Cannot use your own code"}

    # Check if already referred
    c.execute("SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,))
    if c.fetchone():
        conn.close()
        return {"error": "You have already used a referral code"}

    # Create referral and reward both
    c.execute("INSERT INTO referrals (referrer_id, referred_id, rewarded) VALUES (?, ?, 1)",
              (referrer_id, referred_id))
    referral_id = c.lastrowid
    c.execute("UPDATE users SET bonus_mocks = COALESCE(bonus_mocks, 0) + 1 WHERE user_id = ?", (referrer_id,))
    c.execute("UPDATE users SET bonus_mocks = COALESCE(bonus_mocks, 0) + 1 WHERE user_id = ?", (referred_id,))

    conn.commit()

    # Get updated bonus_mocks for sync
    c.execute("SELECT COALESCE(bonus_mocks, 0) as bm FROM users WHERE user_id = ?", (referrer_id,))
    r1 = c.fetchone()
    c.execute("SELECT COALESCE(bonus_mocks, 0) as bm FROM users WHERE user_id = ?", (referred_id,))
    r2 = c.fetchone()
    conn.close()

    sb._fire_and_forget(sb.sync_referral_insert, sqlite_id=referral_id,
                        referrer_id=referrer_id, referred_id=referred_id, rewarded=1)
    sb._fire_and_forget(sb.sync_user_field, user_id=referrer_id,
                        bonus_mocks=r1["bm"] if r1 else 1)
    sb._fire_and_forget(sb.sync_user_field, user_id=referred_id,
                        bonus_mocks=r2["bm"] if r2 else 1)
    return {"success": True}


def get_referral_stats(user_id):
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT referral_code, COALESCE(bonus_mocks, 0) as bonus_mocks FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()

    c.execute("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = ?", (user_id,))
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
    c.execute("SELECT COALESCE(bonus_mocks, 0) as bonus FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row["bonus"] > 0:
        c.execute("UPDATE users SET bonus_mocks = bonus_mocks - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        new_bonus = row["bonus"] - 1
        conn.close()
        sb._fire_and_forget(sb.sync_user_field, user_id=user_id,
                            bonus_mocks=new_bonus)
        return True
    conn.close()
    return False
