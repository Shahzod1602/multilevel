"""
Supabase parallel backup sync for SQLite database.
SQLite remains primary; Supabase (PostgreSQL) is a background cloud backup.
All sync operations are fire-and-forget via ThreadPoolExecutor.
If Supabase is unavailable, the app continues without errors.
Uses psycopg2 for direct PostgreSQL connection (no API key needed).
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)

# Connection string from env
_DSN = None


def _get_dsn():
    global _DSN
    if _DSN is not None:
        return _DSN
    _DSN = os.getenv("SUPABASE_DB_URL", "")
    if not _DSN:
        logger.warning("SUPABASE_DB_URL not set — sync disabled")
    return _DSN


def _get_conn():
    """Get a new psycopg2 connection. Each thread gets its own."""
    import psycopg2
    dsn = _get_dsn()
    if not dsn:
        return None
    return psycopg2.connect(dsn)


def _fire_and_forget(fn, *args, **kwargs):
    """Submit a sync function to the thread pool. Never blocks, never crashes."""
    try:
        _executor.submit(_safe_call, fn, *args, **kwargs)
    except Exception as e:
        logger.error(f"Failed to submit sync task: {e}")


def _safe_call(fn, *args, **kwargs):
    """Wrapper that catches all exceptions so the executor thread never dies."""
    try:
        fn(*args, **kwargs)
    except Exception as e:
        logger.error(f"Supabase sync error in {fn.__name__}: {e}")


# ─── Sync functions (called in background threads) ────────────────


def sync_user(user_id, first_name="", username="", photo_url="",
              contact=None, tariff="free", referral_code=None, bonus_mocks=0,
              created_at=None):
    """Upsert a user row to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, first_name, username, photo_url, contact, tariff, referral_code, bonus_mocks, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    username = COALESCE(EXCLUDED.username, users.username),
                    photo_url = COALESCE(EXCLUDED.photo_url, users.photo_url),
                    contact = COALESCE(EXCLUDED.contact, users.contact),
                    tariff = COALESCE(EXCLUDED.tariff, users.tariff),
                    referral_code = COALESCE(EXCLUDED.referral_code, users.referral_code),
                    bonus_mocks = COALESCE(EXCLUDED.bonus_mocks, users.bonus_mocks)
            """, (user_id, first_name or "", username or "", photo_url or "",
                  contact, tariff or "free", referral_code, bonus_mocks or 0,
                  str(created_at) if created_at else None))
        conn.commit()
    finally:
        conn.close()


def sync_admin(user_id):
    """Upsert an admin row to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
                (user_id,))
        conn.commit()
    finally:
        conn.close()


def sync_user_settings(user_id, **kwargs):
    """Upsert user settings to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        data = {
            "dark_mode": kwargs.get("dark_mode", 0),
            "notifications": kwargs.get("notifications", 1),
            "language": kwargs.get("language", "en"),
            "daily_goal": kwargs.get("daily_goal", 30),
            "target_score": kwargs.get("target_score", 6.5),
            "target_level": kwargs.get("target_level", "B2"),
        }
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_settings (user_id, dark_mode, notifications, language, daily_goal, target_score, target_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    dark_mode = EXCLUDED.dark_mode,
                    notifications = EXCLUDED.notifications,
                    language = EXCLUDED.language,
                    daily_goal = EXCLUDED.daily_goal,
                    target_score = EXCLUDED.target_score,
                    target_level = EXCLUDED.target_level
            """, (user_id, data["dark_mode"], data["notifications"], data["language"],
                  data["daily_goal"], data["target_score"], data["target_level"]))
        conn.commit()
    finally:
        conn.close()


def sync_session_insert(sqlite_id, user_id, session_type="practice", part="1.1",
                        status="active", started_at=None):
    """Insert a new session to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions (sqlite_id, user_id, type, part, status, started_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sqlite_id) DO NOTHING
            """, (sqlite_id, user_id, session_type, part, status,
                  str(started_at) if started_at else None))
        conn.commit()
    finally:
        conn.close()


def sync_session_complete(sqlite_id, scores, feedback, completed_at):
    """Update a completed session in Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sessions SET
                    status = 'completed',
                    score_fluency = %s, score_lexical = %s, score_grammar = %s,
                    score_pronunciation = %s, score_overall = %s,
                    feedback = %s, completed_at = %s
                WHERE sqlite_id = %s
            """, (scores.get("fluency"), scores.get("lexical"), scores.get("grammar"),
                  scores.get("pronunciation"), scores.get("overall"),
                  feedback, str(completed_at), sqlite_id))
        conn.commit()
    finally:
        conn.close()


def sync_response_insert(sqlite_id, session_sqlite_id, question_text,
                         transcription, duration, part, debate_side=None):
    """Insert a response to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO responses (sqlite_id, session_sqlite_id, question_text, transcription, duration, part, debate_side)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sqlite_id) DO NOTHING
            """, (sqlite_id, session_sqlite_id, question_text, transcription,
                  duration or 0, part, debate_side))
        conn.commit()
    finally:
        conn.close()


def sync_attempt_insert(sqlite_id, user_id, attempt_time=None):
    """Insert an attempt to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO attempts (sqlite_id, user_id, attempt_time)
                VALUES (%s, %s, %s)
                ON CONFLICT (sqlite_id) DO NOTHING
            """, (sqlite_id, user_id, str(attempt_time) if attempt_time else None))
        conn.commit()
    finally:
        conn.close()


def sync_daily_study(sqlite_id, user_id, date, minutes, sessions_count):
    """Upsert daily study to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_study (sqlite_id, user_id, date, minutes, sessions_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (sqlite_id) DO UPDATE SET
                    minutes = EXCLUDED.minutes,
                    sessions_count = EXCLUDED.sessions_count
            """, (sqlite_id, user_id, date, minutes, sessions_count))
        conn.commit()
    finally:
        conn.close()


def sync_referral_insert(sqlite_id, referrer_id, referred_id, rewarded=0,
                         created_at=None):
    """Insert a referral to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO referrals (sqlite_id, referrer_id, referred_id, rewarded, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (sqlite_id) DO NOTHING
            """, (sqlite_id, referrer_id, referred_id, rewarded,
                  str(created_at) if created_at else None))
        conn.commit()
    finally:
        conn.close()


def sync_ad_insert(sqlite_id, admin_id, image_path, caption, schedule_time,
                   sent=0):
    """Insert an ad to Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ads (sqlite_id, admin_id, image_path, caption, schedule_time, sent)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sqlite_id) DO NOTHING
            """, (sqlite_id, admin_id, image_path, caption,
                  str(schedule_time), sent))
        conn.commit()
    finally:
        conn.close()


def sync_ad_mark_sent(sqlite_id):
    """Mark an ad as sent in Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE ads SET sent = 1 WHERE sqlite_id = %s", (sqlite_id,))
        conn.commit()
    finally:
        conn.close()


def sync_user_tariff(user_id, tariff):
    """Update user tariff in Supabase."""
    conn = _get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET tariff = %s WHERE user_id = %s",
                        (tariff, user_id))
        conn.commit()
    finally:
        conn.close()


def sync_user_field(user_id, **kwargs):
    """Update specific user fields in Supabase."""
    conn = _get_conn()
    if not conn:
        return
    if not kwargs:
        conn.close()
        return
    try:
        set_parts = []
        values = []
        for k, v in kwargs.items():
            set_parts.append(f"{k} = %s")
            values.append(v)
        values.append(user_id)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE user_id = %s",
                        values)
        conn.commit()
    finally:
        conn.close()


# ─── Restore from Supabase ────────────────────────────────────────


def restore_from_supabase():
    """
    If SQLite is empty (no users), restore all data from Supabase.
    Called at startup after migrations.
    """
    import db as db_module

    pg = _get_conn()
    if not pg:
        logger.info("Supabase not configured — skipping restore")
        return

    sl = db_module.get_connection()
    c = sl.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    sl.close()

    if user_count > 0:
        logger.info(f"SQLite has {user_count} users — skipping restore")
        pg.close()
        return

    logger.info("SQLite is empty — restoring from Supabase...")

    try:
        pgc = pg.cursor()

        # 1. Users
        pgc.execute("SELECT user_id, contact, tariff, created_at, first_name, username, photo_url, referral_code, bonus_mocks FROM users")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute(
                    """INSERT OR IGNORE INTO users
                       (user_id, contact, tariff, created_at, first_name, username, photo_url, referral_code, bonus_mocks)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r[0], r[1], r[2] or "free", str(r[3]) if r[3] else None,
                     r[4] or "", r[5] or "", r[6] or "", r[7], r[8] or 0))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} users")

        # 2. Admins
        pgc.execute("SELECT user_id FROM admins")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (r[0],))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} admins")

        # 3. User settings
        pgc.execute("SELECT user_id, dark_mode, notifications, language, daily_goal, target_score, target_level FROM user_settings")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute(
                    """INSERT OR IGNORE INTO user_settings
                       (user_id, dark_mode, notifications, language, daily_goal, target_score, target_level)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (r[0], r[1] or 0, r[2] if r[2] is not None else 1,
                     r[3] or "en", r[4] or 30, r[5] or 6.5, r[6] or "B2"))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} user_settings")

        # 4. Sessions
        pgc.execute("""SELECT sqlite_id, user_id, type, part, status,
                              score_fluency, score_lexical, score_grammar,
                              score_pronunciation, score_overall, feedback,
                              started_at, completed_at
                       FROM sessions ORDER BY sqlite_id""")
        rows = pgc.fetchall()
        session_id_map = {}
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute(
                    """INSERT INTO sessions
                       (user_id, type, part, status, score_fluency, score_lexical,
                        score_grammar, score_pronunciation, score_overall, feedback,
                        started_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (r[1], r[2] or "practice", r[3] or "1.1", r[4] or "active",
                     r[5], r[6], r[7], r[8], r[9], r[10],
                     str(r[11]) if r[11] else None,
                     str(r[12]) if r[12] else None))
                session_id_map[r[0]] = c.lastrowid
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} sessions")

        # 5. Responses
        pgc.execute("""SELECT sqlite_id, session_sqlite_id, question_text,
                              transcription, duration, part, debate_side, created_at
                       FROM responses ORDER BY sqlite_id""")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                session_id = session_id_map.get(r[1], r[1])
                c.execute(
                    """INSERT INTO responses
                       (session_id, question_text, transcription, duration, part, debate_side, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, r[2], r[3], r[4] or 0, r[5] or "1", r[6],
                     str(r[7]) if r[7] else None))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} responses")

        # 6. Attempts
        pgc.execute("SELECT sqlite_id, user_id, attempt_time FROM attempts ORDER BY sqlite_id")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute("INSERT INTO attempts (user_id, attempt_time) VALUES (?, ?)",
                          (r[1], str(r[2]) if r[2] else None))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} attempts")

        # 7. Daily study
        pgc.execute("SELECT sqlite_id, user_id, date, minutes, sessions_count FROM daily_study ORDER BY sqlite_id")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute(
                    """INSERT OR IGNORE INTO daily_study (user_id, date, minutes, sessions_count)
                       VALUES (?, ?, ?, ?)""",
                    (r[1], r[2], r[3] or 0, r[4] or 0))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} daily_study")

        # 8. Referrals
        pgc.execute("SELECT sqlite_id, referrer_id, referred_id, rewarded, created_at FROM referrals ORDER BY sqlite_id")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute(
                    """INSERT INTO referrals (referrer_id, referred_id, rewarded, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (r[1], r[2], r[3] or 0, str(r[4]) if r[4] else None))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} referrals")

        # 9. Ads
        pgc.execute("SELECT sqlite_id, admin_id, image_path, caption, schedule_time, sent FROM ads ORDER BY sqlite_id")
        rows = pgc.fetchall()
        if rows:
            sl = db_module.get_connection()
            c = sl.cursor()
            for r in rows:
                c.execute(
                    """INSERT INTO ads (admin_id, image_path, caption, schedule_time, sent)
                       VALUES (?, ?, ?, ?, ?)""",
                    (r[1], r[2], r[3], str(r[4]) if r[4] else None, r[5] or 0))
            sl.commit()
            sl.close()
            logger.info(f"Restored {len(rows)} ads")

        pgc.close()
        logger.info("Restore from Supabase completed successfully")

    except Exception as e:
        logger.error(f"Restore from Supabase failed: {e}")
    finally:
        pg.close()


# ─── Full sync (existing data → Supabase) ─────────────────────────


def full_sync_to_supabase():
    """
    One-time sync of ALL existing SQLite data to Supabase.
    Call this manually or at first deploy.
    """
    import db as db_module

    pg = _get_conn()
    if not pg:
        logger.error("Supabase not configured — cannot sync")
        return

    sl = db_module.get_connection()
    c = sl.cursor()

    try:
        # Users
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_user(
                user_id=r["user_id"],
                first_name=r.get("first_name", ""),
                username=r.get("username", ""),
                photo_url=r.get("photo_url", ""),
                contact=r.get("contact"),
                tariff=r.get("tariff", "free"),
                referral_code=r.get("referral_code"),
                bonus_mocks=r.get("bonus_mocks", 0),
                created_at=r.get("created_at"),
            )
        logger.info(f"Synced {len(rows)} users")

        # Admins
        c.execute("SELECT * FROM admins")
        rows = c.fetchall()
        for r in rows:
            sync_admin(r["user_id"])
        logger.info(f"Synced {len(rows)} admins")

        # User settings
        c.execute("SELECT * FROM user_settings")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_user_settings(**r)
        logger.info(f"Synced {len(rows)} user_settings")

        # Sessions
        c.execute("SELECT * FROM sessions")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_session_insert(
                sqlite_id=r["id"],
                user_id=r["user_id"],
                session_type=r.get("type", "practice"),
                part=r.get("part", "1.1"),
                status=r.get("status", "active"),
                started_at=r.get("started_at"),
            )
            if r.get("status") == "completed":
                scores = {
                    "fluency": r.get("score_fluency"),
                    "lexical": r.get("score_lexical"),
                    "grammar": r.get("score_grammar"),
                    "pronunciation": r.get("score_pronunciation"),
                    "overall": r.get("score_overall"),
                }
                sync_session_complete(r["id"], scores, r.get("feedback"),
                                      r.get("completed_at"))
        logger.info(f"Synced {len(rows)} sessions")

        # Responses
        c.execute("SELECT * FROM responses")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_response_insert(
                sqlite_id=r["id"],
                session_sqlite_id=r["session_id"],
                question_text=r.get("question_text"),
                transcription=r.get("transcription"),
                duration=r.get("duration", 0),
                part=r.get("part", "1"),
                debate_side=r.get("debate_side"),
            )
        logger.info(f"Synced {len(rows)} responses")

        # Attempts
        c.execute("SELECT * FROM attempts")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_attempt_insert(
                sqlite_id=r["id"],
                user_id=r["user_id"],
                attempt_time=r.get("attempt_time"),
            )
        logger.info(f"Synced {len(rows)} attempts")

        # Daily study
        c.execute("SELECT * FROM daily_study")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_daily_study(
                sqlite_id=r["id"],
                user_id=r["user_id"],
                date=r["date"],
                minutes=r.get("minutes", 0),
                sessions_count=r.get("sessions_count", 0),
            )
        logger.info(f"Synced {len(rows)} daily_study")

        # Referrals
        c.execute("SELECT * FROM referrals")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_referral_insert(
                sqlite_id=r["id"],
                referrer_id=r["referrer_id"],
                referred_id=r["referred_id"],
                rewarded=r.get("rewarded", 0),
                created_at=r.get("created_at"),
            )
        logger.info(f"Synced {len(rows)} referrals")

        # Ads
        c.execute("SELECT * FROM ads")
        rows = c.fetchall()
        for r in rows:
            r = dict(r)
            sync_ad_insert(
                sqlite_id=r["id"],
                admin_id=r["admin_id"],
                image_path=r.get("image_path"),
                caption=r.get("caption"),
                schedule_time=r.get("schedule_time"),
                sent=r.get("sent", 0),
            )
        logger.info(f"Synced {len(rows)} ads")

        logger.info("Full sync to Supabase completed")

    except Exception as e:
        logger.error(f"Full sync failed: {e}")
    finally:
        sl.close()
        pg.close()
