"""
FastAPI backend for IELTS Speaking Telegram Mini App.
Provides REST API with Telegram initData authentication.
"""
import os
import json
import hmac
import hashlib
import tempfile
import subprocess
import asyncio
import logging
from datetime import datetime
from urllib.parse import parse_qs, unquote

import aiohttp
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional

import db

logger = logging.getLogger(__name__)

app = FastAPI(title="IELTS Speaking Mini App")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel - clear English voice

# Load questions
QUESTIONS = []
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        QUESTIONS = data if isinstance(data, list) else data.get("questions", [])
except FileNotFoundError:
    logger.warning("questions.json not found")


# ─── Telegram Auth ─────────────────────────────────────────────

def validate_init_data(init_data: str) -> dict:
    """Validate Telegram Mini App initData using HMAC-SHA256."""
    init_data = init_data.strip()

    # Parse into raw (URL-encoded) and decoded key-value pairs
    raw_dict = {}
    decoded_dict = {}
    for pair in init_data.split("&"):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        raw_dict[key] = value
        decoded_dict[key] = unquote(value)

    logger.info(f"Auth keys: {sorted(raw_dict.keys())}")

    received_hash = raw_dict.pop("hash", None)
    decoded_dict.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    secret_key = hmac.new(b"WebAppData", TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()

    # Try decoded values first (standard approach)
    dcs_decoded = "\n".join(f"{k}={v}" for k, v in sorted(decoded_dict.items()))
    hash_decoded = hmac.new(secret_key, dcs_decoded.encode(), hashlib.sha256).hexdigest()

    # Try raw (URL-encoded) values as fallback
    dcs_raw = "\n".join(f"{k}={v}" for k, v in sorted(raw_dict.items()))
    hash_raw = hmac.new(secret_key, dcs_raw.encode(), hashlib.sha256).hexdigest()

    logger.info(f"Received hash: {received_hash[:20]}...")
    logger.info(f"Hash (decoded): {hash_decoded[:20]}...")
    logger.info(f"Hash (raw/enc): {hash_raw[:20]}...")
    logger.info(f"Token len={len(TELEGRAM_TOKEN)}, starts={TELEGRAM_TOKEN[:15]}")
    logger.info(f"DCS decoded (first 300): {dcs_decoded[:300]}")

    if hmac.compare_digest(hash_decoded, received_hash):
        logger.info("Auth OK (decoded values)")
        user_data_str = decoded_dict.get("user")
    elif hmac.compare_digest(hash_raw, received_hash):
        logger.info("Auth OK (raw values)")
        user_data_str = unquote(raw_dict.get("user", ""))
    else:
        logger.warning("Hash mismatch — neither decoded nor raw matched")
        raise HTTPException(status_code=401, detail="Invalid hash")

    if not user_data_str:
        raise HTTPException(status_code=401, detail="Missing user data")

    user_data = json.loads(user_data_str)
    return user_data


async def get_current_user(request: Request) -> dict:
    """Dependency: extract and validate user from Authorization header."""
    auth = request.headers.get("Authorization", "")

    # Support both "tma <data>" and raw initData
    if auth.startswith("tma "):
        init_data = auth[4:]
    elif auth:
        init_data = auth
    else:
        raise HTTPException(status_code=401, detail="Missing authorization")

    user_data = validate_init_data(init_data)

    user = db.get_or_create_user(
        user_id=user_data["id"],
        first_name=user_data.get("first_name", ""),
        username=user_data.get("username", ""),
        photo_url=user_data.get("photo_url", ""),
    )
    return user


# ─── Models ────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    dark_mode: Optional[bool] = None
    notifications: Optional[bool] = None
    language: Optional[str] = None
    daily_goal: Optional[int] = None


class SessionStart(BaseModel):
    type: str = "practice"
    part: int = 1


# ─── Debug Endpoint ───────────────────────────────────────────

@app.get("/api/debug/auth")
async def debug_auth(request: Request):
    """Debug endpoint to inspect auth header and validation."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("tma "):
        init_data = auth[4:]
    else:
        init_data = auth

    # Show raw data
    pairs = init_data.split("&")
    raw_keys = [p.split("=", 1)[0] for p in pairs if "=" in p]

    return {
        "auth_header_length": len(auth),
        "init_data_length": len(init_data),
        "raw_first_100": init_data[:100],
        "keys": raw_keys,
        "token_first_15": TELEGRAM_TOKEN[:15],
        "token_length": len(TELEGRAM_TOKEN),
    }


# ─── API Endpoints ─────────────────────────────────────────────

@app.get("/api/user/me")
async def get_me(user=Depends(get_current_user)):
    settings = db.get_user_settings(user["user_id"])
    total_sessions = db.get_total_sessions(user["user_id"])
    total_hours = db.get_total_practice_hours(user["user_id"])
    return {
        "user": {
            "user_id": user["user_id"],
            "first_name": user["first_name"],
            "username": user["username"],
            "photo_url": user["photo_url"],
            "tariff": user["tariff"],
            "created_at": user["created_at"],
        },
        "settings": settings,
        "stats": {
            "total_sessions": total_sessions,
            "total_hours": total_hours,
        }
    }


@app.put("/api/user/settings")
async def update_settings(body: SettingsUpdate, user=Depends(get_current_user)):
    updates = {}
    if body.dark_mode is not None:
        updates["dark_mode"] = 1 if body.dark_mode else 0
    if body.notifications is not None:
        updates["notifications"] = 1 if body.notifications else 0
    if body.language is not None:
        updates["language"] = body.language
    if body.daily_goal is not None:
        updates["daily_goal"] = body.daily_goal

    if updates:
        db.update_user_settings(user["user_id"], **updates)

    return db.get_user_settings(user["user_id"])


@app.get("/api/questions")
async def get_questions(part: int = 1, user=Depends(get_current_user)):
    filtered = [q for q in QUESTIONS if q.get("part") == part]
    return {"questions": filtered, "total": len(filtered)}


@app.post("/api/sessions/start")
async def start_session(body: SessionStart, user=Depends(get_current_user)):
    session_id = db.create_session(user["user_id"], body.type, body.part)

    # Pick questions for this session
    part = body.part
    filtered = [q for q in QUESTIONS if q.get("part") == part]
    import random
    if part == 1:
        questions = random.sample(filtered, min(4, len(filtered)))
    elif part == 2:
        questions = random.sample(filtered, min(1, len(filtered)))
    else:
        questions = random.sample(filtered, min(4, len(filtered)))

    return {
        "session_id": session_id,
        "questions": questions,
    }


@app.post("/api/sessions/{session_id}/respond")
async def session_respond(
    session_id: int,
    audio: UploadFile = File(...),
    question: str = Form(""),
    part: int = Form(1),
    user=Depends(get_current_user),
):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["user_id"] != user["user_id"]:
        raise HTTPException(403, "Not your session")

    # Save audio to temp file
    audio_data = await audio.read()
    if len(audio_data) < 1000:
        raise HTTPException(400, "Audio too short")

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_data)
        tmp.flush()
        audio_path = tmp.name

    wav_path = audio_path.replace(".webm", ".wav")

    try:
        # Convert webm to wav for Groq compatibility
        convert_result = subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if convert_result.returncode != 0:
            logger.error(f"FFmpeg convert error: {convert_result.stderr}")
            raise HTTPException(400, "Audio conversion failed")

        # Transcribe with Groq Whisper API
        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)

        with open(wav_path, "rb") as audio_file:
            transcription_result = groq_client.audio.transcriptions.create(
                file=(wav_path, audio_file.read()),
                model="whisper-large-v3",
                language="en",
                prompt=f"IELTS Speaking Part {part} response to: {question}",
            )
        transcription = transcription_result.text.strip()

        if not transcription:
            raise HTTPException(400, "Could not transcribe audio")

        # Get audio duration via ffprobe
        duration_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", wav_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            duration = int(float(duration_result.stdout.strip()))
        except (ValueError, TypeError):
            duration = 0

        db.add_response(session_id, question, transcription, duration, part)

        return {
            "transcription": transcription,
            "duration": duration,
        }

    finally:
        for f in [audio_path, wav_path]:
            try:
                os.remove(f)
            except OSError:
                pass


@app.post("/api/sessions/{session_id}/complete")
async def complete_session(session_id: int, user=Depends(get_current_user)):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["user_id"] != user["user_id"]:
        raise HTTPException(403, "Not your session")

    responses = db.get_session_responses(session_id)
    if not responses:
        raise HTTPException(400, "No responses in session")

    # Build GPT prompt
    prompt = (
        "You are a certified IELTS Speaking examiner. Analyze the following responses.\n"
        "Score each criterion 0-9 (half-points allowed):\n"
        "1. Fluency and Coherence\n2. Lexical Resource\n"
        "3. Grammatical Range and Accuracy\n4. Pronunciation\n\n"
        "Return ONLY valid JSON (no markdown, no code fences) in this format:\n"
        '{"fluency": 6.5, "lexical": 6.0, "grammar": 5.5, "pronunciation": 6.0, '
        '"overall": 6.0, "feedback": "Your detailed feedback here."}\n\n'
        "Responses:\n"
    )

    for r in responses:
        prompt += (
            f"\nPart {r['part']}:\n"
            f"Question: {r['question_text']}\n"
            f"Answer: {r['transcription']}\n"
            f"Duration: {r['duration']}s\n"
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a certified IELTS Speaking examiner. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5,
        )
        content = response.choices[0].message.content.strip()

        # Try to parse JSON from response
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        scores_data = json.loads(content)
        scores = {
            "fluency": scores_data.get("fluency", 0),
            "lexical": scores_data.get("lexical", 0),
            "grammar": scores_data.get("grammar", 0),
            "pronunciation": scores_data.get("pronunciation", 0),
            "overall": scores_data.get("overall", 0),
        }
        feedback = scores_data.get("feedback", "")

        db.complete_session(session_id, scores, feedback)

        return {
            "scores": scores,
            "feedback": feedback,
        }

    except json.JSONDecodeError:
        # If GPT didn't return valid JSON, provide default scores
        scores = {"fluency": 5.0, "lexical": 5.0, "grammar": 4.5, "pronunciation": 5.0, "overall": 5.0}
        feedback = content if content else "Unable to generate detailed feedback."
        db.complete_session(session_id, scores, feedback)
        return {"scores": scores, "feedback": feedback}

    except Exception as e:
        logger.error(f"GPT feedback error: {e}")
        raise HTTPException(500, f"Feedback generation failed: {str(e)}")


@app.get("/api/progress/weekly")
async def weekly_progress(user=Depends(get_current_user)):
    days = db.get_weekly_progress(user["user_id"])
    recent = db.get_recent_sessions(user["user_id"], limit=7)
    return {
        "days": days,
        "recent_sessions": recent,
    }


@app.get("/api/progress/streak")
async def study_streak(user=Depends(get_current_user)):
    streak = db.get_study_streak(user["user_id"])
    total_sessions = db.get_total_sessions(user["user_id"])
    total_hours = db.get_total_practice_hours(user["user_id"])
    return {
        "streak": streak,
        "total_sessions": total_sessions,
        "total_hours": total_hours,
    }


@app.get("/api/content/tips")
async def get_tips(user=Depends(get_current_user)):
    return {
        "tips": [
            {
                "title": "Part 1: Keep it Natural",
                "content": "Answer in 2-3 sentences. Don't memorize scripts. Be yourself and speak naturally.",
                "icon": "chat"
            },
            {
                "title": "Part 2: Use the Minute",
                "content": "Use your 1-minute preparation time wisely. Make brief notes on key points you want to cover.",
                "icon": "edit"
            },
            {
                "title": "Part 3: Go Deeper",
                "content": "Give developed answers with examples and explanations. Show you can discuss abstract topics.",
                "icon": "lightbulb"
            },
            {
                "title": "Vocabulary: Topic Words",
                "content": "Learn vocabulary by topic (education, technology, environment). Use collocations naturally.",
                "icon": "book"
            },
            {
                "title": "Fluency: Don't Panic",
                "content": "It's okay to pause briefly. Use fillers like 'Well...', 'That's an interesting question...'",
                "icon": "mic"
            },
            {
                "title": "Grammar: Mix it Up",
                "content": "Use a range of structures: conditionals, passive voice, relative clauses. Accuracy matters more than complexity.",
                "icon": "check"
            },
        ]
    }


# ─── TTS (ElevenLabs) ─────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts")
async def text_to_speech(body: TTSRequest, user=Depends(get_current_user)):
    if not ELEVENLABS_KEY:
        raise HTTPException(500, "TTS not configured")

    if len(body.text) > 500:
        raise HTTPException(400, "Text too long")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": body.text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"ElevenLabs error: {resp.status} {error_text}")
                    raise HTTPException(502, "TTS generation failed")
                audio_data = await resp.read()
                return Response(content=audio_data, media_type="audio/mpeg")
    except aiohttp.ClientError as e:
        logger.error(f"ElevenLabs request error: {e}")
        raise HTTPException(502, "TTS service unavailable")


# ─── Static files (frontend) ──────────────────────────────────

# Serve webapp folder
webapp_dir = os.path.join(os.path.dirname(__file__), "webapp")
if os.path.isdir(webapp_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(webapp_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(webapp_dir, "js")), name="js")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(webapp_dir, "index.html"))
