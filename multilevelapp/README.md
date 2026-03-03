# IELTS Speaking Practice App

Telegram Mini App for practicing IELTS Speaking exam with AI-powered feedback.

## Features

- **Mock Test** — Full IELTS Speaking test (Part 1, 2, 3) with AI scoring
- **Practice** — Practice individual parts with topic filtering
- **AI Scoring** — Band scores for Fluency, Lexical, Grammar, Pronunciation
- **Grammar Highlighting** — AI detects and explains grammar errors
- **Pronunciation Tips** — Word-level pronunciation feedback
- **Sample Answers** — Band 7+ model answers from GPT
- **Part 2 Cue Card** — Yellow cue card with 1-min prep timer
- **AI Follow-up** — GPT generates follow-up questions for Part 3
- **WPM Stats** — Words per minute tracking
- **History** — View past sessions with detailed scores
- **Band Score Target** — Set target and track progress
- **Daily Limits** — Free: 2 mock/day, Premium: 5 mock/day, Practice: unlimited
- **TTS Voices** — 4 voice options (Sarah, Lily, Charlie, Roger)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Bot | python-telegram-bot |
| Database | PostgreSQL (local) + Supabase (backup) |
| Frontend | Vanilla JS SPA |
| Speech-to-Text | Groq Whisper Large V3 |
| AI Scoring | OpenAI GPT-4o-mini |
| Text-to-Speech | Edge TTS (free) |
| Audio Processing | FFmpeg |
| Deployment | Docker Compose, Nginx, Let's Encrypt |

## Architecture

```
Telegram Mini App (Browser)
        |
     Nginx (SSL)
        |
   FastAPI (port 8000)
    /         \
PostgreSQL   External APIs
(local host) - Groq (Whisper)
     |         - OpenAI (GPT-4o-mini)
  Supabase     - Edge TTS
 (backup/2h)
```

## Project Structure

```
multilevelapp/
├── app.py              # Telegram bot
├── web_server.py       # FastAPI REST API
├── db.py               # Database helpers (PostgreSQL + connection pool)
├── supabase_sync.py    # Supabase backup/restore (every 2 hours)
├── run.py              # Entry point (starts bot + web server)
├── questions.json      # IELTS question bank
├── bot.db              # SQLite database
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
├── nginx/
│   └── conf.d/
│       └── default.conf
└── webapp/
    ├── index.html
    ├── css/
    │   └── styles.css
    └── js/
        ├── app.js          # SPA router
        ├── api.js          # API client with Telegram auth
        └── pages/
            ├── home.js
            ├── practice.js
            ├── mock-test.js
            ├── progress.js
            ├── profile.js
            └── history.js
```

## Setup

### 1. Environment Variables

Create `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
CHANNEL_USERNAME=@your_channel
WEBAPP_URL=https://your-domain.com
WEB_PORT=8000
DATABASE_URL=postgresql://multilevel:password@host.docker.internal:5432/multilevel
SUPABASE_DB_URL=postgresql://postgres.xxx:password@aws-region.pooler.supabase.com:6543/postgres
```

### 2. Deploy with Docker

```bash
docker compose up -d --build
```

### 3. SSL Certificate

```bash
docker compose run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  -d your-domain.com
docker restart ielts-nginx
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/user` | Get/create user (Telegram auth) |
| GET | `/api/user/settings` | Get user settings |
| PUT | `/api/user/settings` | Update settings |
| POST | `/api/sessions/start` | Start practice/mock session |
| POST | `/api/sessions/{id}/respond` | Upload voice response |
| POST | `/api/sessions/{id}/complete` | Get AI scoring |
| GET | `/api/progress/streak` | Get study streak & stats |
| GET | `/api/progress/weekly` | Weekly study chart data |
| GET | `/api/topics` | Get topics for a part |
| GET | `/api/session-info` | Daily mock limit info |
| GET | `/api/history` | Past sessions list |
| GET | `/api/history/{id}` | Session detail |
| POST | `/api/follow-up` | Generate follow-up question |
| POST | `/api/sample-answer` | Generate sample answer |
| POST | `/api/tts` | Text-to-speech |

## Admin Commands (Telegram Bot)

| Command | Description |
|---------|-------------|
| `/upgrade_gold @username` | Upgrade user to Premium |
| `/downgrade @username` | Downgrade to Free |
| `/admin_add <user_id>` | Add new admin |
| `/send_all <message>` | Broadcast to all users |
| `/stats` | Bot statistics |

## Server Requirements

| | Minimal | Recommended |
|---|---------|-------------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 20 GB SSD | 40 GB SSD |

## Cost Per User

### API Pricing

| Service | Model | Price |
|---------|-------|-------|
| Groq | Whisper Large V3 | $0.111 / hour audio |
| OpenAI | GPT-4o-mini | $0.15/1M input, $0.60/1M output tokens |
| Edge TTS | Microsoft Edge | **Free** |
| gTTS | Google TTS | **Free** |

### Cost Per Session

| Session Type | Groq (STT) | OpenAI (Scoring) | Total |
|-------------|------------|-----------------|-------|
| **Mock Test** (9 responses, ~9 min audio) | $0.017 | $0.0007 | **~$0.018** |
| **Practice** (1 response, ~1.5 min audio) | $0.003 | $0.0006 | **~$0.004** |
| Sample Answer (optional) | — | $0.0003 | $0.0003 |
| Follow-up Question (optional) | — | $0.0001 | $0.0001 |

### Monthly Cost Per Active User

Average user: **2 mock tests + 10 practice sessions / month**

| Item | Cost |
|------|------|
| Mock tests (2x) | $0.036 |
| Practice (10x) | $0.040 |
| **Total per user/month** | **~$0.08** |

### Total Monthly Cost

| Active Users | API Cost | Server | Total |
|-------|----------|--------|-------|
| 100 | $8 | $7 | **$15/mo** |
| 500 | $40 | $7 | **$47/mo** |
| 1,000 | $80 | $12 | **$92/mo** |

> Groq has a generous free tier. With free tier, cost drops to ~$0.001/user/month (OpenAI only).

## Changelog

### 2026-03-03 — Performance & PostgreSQL Migration

**Database migration: SQLite → PostgreSQL**
- `db.py` completely rewritten using `psycopg2` with `ThreadedConnectionPool(2, 10)`
- `_Conn` wrapper returns connections back to pool automatically
- All `?` placeholders → `%s`, `AUTOINCREMENT` → `SERIAL`, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- `lastrowid` → `RETURNING id` for insert ID retrieval
- `RealDictCursor` for dict-style row access everywhere

**Supabase demoted to backup-only**
- Removed all real-time `sb._fire_and_forget(...)` sync calls from db.py (was causing ~500ms delay on every DB write)
- Supabase now syncs in background every 2 hours via `run_supabase_sync_loop()` in `run.py`
- On fresh deploy, data is restored from Supabase automatically (`restore_from_supabase()`)

**Query optimizations**
- `get_weekly_progress`: 7 separate queries → 1 query using `ANY(%s)`
- `get_user_limits`: 4 separate DB connections → 1 connection
- User settings: sync only on first create, not on every read

**Frontend performance (webapp/js/app.js)**
- Parallel API calls on init: `Promise.all([/api/user/me, /api/check-subscription])`
- Subscription check cache (5-minute TTL) — no API call on every page navigation
- Force re-check only when user clicks "Tekshirish" button
- Removed verbose `console.log` of initData

**Backend (web_server.py)**
- Removed 6 verbose `logger.info` lines from `validate_init_data()` (runs on every request)

**Deployment**
- `docker-compose.yml`: removed PostgreSQL container, added `extra_hosts: host.docker.internal:host-gateway` to connect to host's PostgreSQL
- PostgreSQL installed on host server with dedicated `multilevel` user and database
