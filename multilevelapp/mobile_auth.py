"""
Mobile app authentication helpers (Multilevel Speaking).

Telegram Mini App keeps using initData. The native mobile app (Capacitor)
goes through this two-step flow:

  1. App calls POST /api/auth/start → returns a random `state` string.
  2. App opens https://t.me/<bot>?start=mlogin_<state>.
  3. Bot's /start handler verifies the user and calls `complete_login(state, user_id)`.
  4. App polls GET /api/auth/exchange?state=<state> until a JWT is returned.
  5. App stores the JWT and sends it as `Authorization: Bearer <jwt>`.

State is held in-memory: this only works because the bot and web server
run in one process (see run.py). Entries expire after STATE_TTL_SECONDS.
"""
import os
import secrets
import time
from typing import Optional

import jwt

JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("TELEGRAM_BOT_TOKEN", "dev-secret")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

STATE_TTL_SECONDS = 5 * 60  # 5 minutes

# state -> { "created_at": ts, "user_id": int|None }
_pending: dict[str, dict] = {}


def _gc():
    now = time.time()
    expired = [s for s, v in _pending.items() if now - v["created_at"] > STATE_TTL_SECONDS]
    for s in expired:
        _pending.pop(s, None)


def create_state() -> str:
    _gc()
    state = secrets.token_urlsafe(24)
    _pending[state] = {"created_at": time.time(), "user_id": None}
    return state


def complete_login(state: str, user_id: int) -> bool:
    """Called from the bot after /start mlogin_<state>."""
    _gc()
    entry = _pending.get(state)
    if not entry:
        return False
    entry["user_id"] = user_id
    return True


def consume_state(state: str) -> Optional[int]:
    """Return the user_id once the bot has confirmed, then drop the state."""
    _gc()
    entry = _pending.get(state)
    if not entry or entry["user_id"] is None:
        return None
    _pending.pop(state, None)
    return entry["user_id"]


def issue_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
