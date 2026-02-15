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
EDGE_TTS_VOICES = {
    "sarah": "en-US-JennyNeural",
    "lily": "en-GB-SoniaNeural",
    "charlie": "en-US-ChristopherNeural",
    "roger": "en-GB-RyanNeural",
}

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
    target_score: Optional[float] = None


class SessionStart(BaseModel):
    type: str = "practice"
    part: int = 1
    topic: Optional[str] = None


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
    if body.target_score is not None:
        updates["target_score"] = body.target_score

    if updates:
        db.update_user_settings(user["user_id"], **updates)

    return db.get_user_settings(user["user_id"])


@app.get("/api/questions")
async def get_questions(part: int = 1, user=Depends(get_current_user)):
    filtered = [q for q in QUESTIONS if q.get("part") == part]
    return {"questions": filtered, "total": len(filtered)}


@app.get("/api/session-info")
async def session_info(user=Depends(get_current_user)):
    tariff = user.get("tariff", "free")
    is_premium = tariff != "free"
    mock_count = db.get_daily_mock_count(user["user_id"])
    mock_limit = MOCK_LIMIT_PREMIUM if is_premium else MOCK_LIMIT_FREE
    return {
        "mock_today": mock_count,
        "mock_limit": mock_limit,
        "mock_remaining": max(0, mock_limit - mock_count),
        "is_premium": is_premium,
        "tariff": tariff,
    }


@app.get("/api/topics")
async def get_topics(part: int = 1, user=Depends(get_current_user)):
    filtered = [q for q in QUESTIONS if q.get("part") == part]
    topics = sorted(set(q.get("topic", "General") for q in filtered))
    return {"topics": topics, "total": len(topics)}


MOCK_LIMIT_FREE = 2
MOCK_LIMIT_PREMIUM = 5

@app.post("/api/sessions/start")
async def start_session(body: SessionStart, user=Depends(get_current_user)):
    # Check daily mock limit
    if body.type == "mock":
        mock_count = db.get_daily_mock_count(user["user_id"])
        is_premium = user.get("tariff", "free") != "free"
        limit = MOCK_LIMIT_PREMIUM if is_premium else MOCK_LIMIT_FREE
        if mock_count >= limit:
            if is_premium:
                raise HTTPException(403, f"Daily mock limit reached ({MOCK_LIMIT_PREMIUM}/day).")
            else:
                raise HTTPException(403, f"Daily mock limit reached ({MOCK_LIMIT_FREE}/day). Upgrade to Premium for {MOCK_LIMIT_PREMIUM} mocks per day!")

    session_id = db.create_session(user["user_id"], body.type, body.part)

    # Pick questions for this session
    part = body.part
    filtered = [q for q in QUESTIONS if q.get("part") == part]
    if body.topic:
        topic_filtered = [q for q in filtered if q.get("topic") == body.topic]
        if topic_filtered:
            filtered = topic_filtered
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

    # Save audio to temp file — detect extension from content type
    audio_data = await audio.read()
    if len(audio_data) < 1000:
        raise HTTPException(400, "Audio too short")

    # Map content type to extension
    ct = (audio.content_type or "").lower()
    ext_map = {
        "audio/webm": ".webm", "audio/ogg": ".ogg",
        "audio/mp4": ".m4a", "audio/mpeg": ".mp3",
        "audio/wav": ".wav", "audio/x-wav": ".wav",
    }
    ext = ext_map.get(ct.split(";")[0], ".ogg")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_data)
        tmp.flush()
        audio_path = tmp.name

    wav_path = audio_path + ".wav"

    try:
        # Convert to wav for Groq compatibility
        convert_result = subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # If conversion fails, try sending original directly to Groq
        use_path = wav_path if convert_result.returncode == 0 else audio_path

        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)

        with open(use_path, "rb") as audio_file:
            transcription_result = groq_client.audio.transcriptions.create(
                file=(use_path, audio_file.read()),
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
             "-of", "default=noprint_wrappers=1:nokey=1", use_path],
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


class CompleteRequest(BaseModel):
    level: str = "intermediate"
    mood: str = "normal"

@app.post("/api/sessions/{session_id}/complete")
async def complete_session(session_id: int, body: CompleteRequest = CompleteRequest(), user=Depends(get_current_user)):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session["user_id"] != user["user_id"]:
        raise HTTPException(403, "Not your session")

    responses = db.get_session_responses(session_id)
    if not responses:
        raise HTTPException(400, "No responses in session")

    # Level-based scoring instructions
    level_instructions = {
        "beginner": (
            "You are scoring a BEGINNER-level English learner (A2-B1). "
            "Be encouraging and lenient. Focus on what they did well. "
            "Give scores that reflect their effort — even simple but clear answers deserve 5.0-6.0. "
            "Only give below 4.0 if the response is mostly unintelligible. "
            "Provide constructive, simple feedback with easy-to-understand suggestions."
        ),
        "intermediate": (
            "You are scoring an INTERMEDIATE-level English learner (B1-B2). "
            "Apply standard IELTS scoring criteria fairly. "
            "Acknowledge strengths while pointing out areas for improvement. "
            "Most responses at this level should score between 5.0-7.0."
        ),
        "advanced": (
            "You are scoring an ADVANCED-level English learner (C1-C2). "
            "Be strict and apply rigorous IELTS scoring standards. "
            "Expect sophisticated vocabulary, complex grammar, natural fluency, and clear pronunciation. "
            "Deduct for any hesitation, repetition, limited vocabulary, or grammatical errors. "
            "Only give 7.0+ for truly excellent performance. Provide detailed, critical feedback."
        ),
    }

    level = body.level if body.level in level_instructions else "intermediate"
    level_text = level_instructions[level]

    mood_instructions = {
        "happy": (
            "You are in a HAPPY, generous mood today. "
            "You see the best in every answer. Add +0.5 bonus to each score criterion. "
            "Your feedback should be very positive and encouraging, highlighting strengths."
        ),
        "normal": "",
        "angry": (
            "You are in a STRICT, harsh mood today. "
            "You are very critical of every mistake. Deduct 1.0 point from each score criterion. "
            "Your feedback should be blunt and focus heavily on errors and weaknesses."
        ),
    }
    mood = body.mood if body.mood in mood_instructions else "normal"
    mood_text = mood_instructions[mood]

    # Build GPT prompt
    mood_section = f"{mood_text}\n\n" if mood_text else ""
    prompt = (
        f"You are a certified IELTS Speaking examiner.\n"
        f"{level_text}\n\n"
        f"{mood_section}"
        "Analyze the following responses.\n"
        "Score each criterion 0-9 (half-points allowed):\n"
        "1. Fluency and Coherence\n2. Lexical Resource\n"
        "3. Grammatical Range and Accuracy\n4. Pronunciation\n\n"
        "Return ONLY valid JSON (no markdown, no code fences) in this format:\n"
        '{"fluency": 6.5, "lexical": 6.0, "grammar": 5.5, "pronunciation": 6.0, '
        '"overall": 6.0, "feedback": "Your detailed feedback here.", '
        '"grammar_corrections": [{"original": "wrong phrase", "corrected": "correct phrase", "explanation": "brief reason"}], '
        '"pronunciation_issues": [{"word": "word", "tip": "pronunciation tip"}]}\n\n'
        "Include up to 5 grammar corrections and up to 3 pronunciation tips.\n\n"
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
            max_tokens=800,
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
        grammar_corrections = scores_data.get("grammar_corrections", [])
        pronunciation_issues = scores_data.get("pronunciation_issues", [])

        db.complete_session(session_id, scores, feedback)

        return {
            "scores": scores,
            "feedback": feedback,
            "grammar_corrections": grammar_corrections,
            "pronunciation_issues": pronunciation_issues,
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


@app.get("/api/history")
async def get_history(user=Depends(get_current_user)):
    sessions = db.get_all_sessions(user["user_id"])
    return {"sessions": sessions}


@app.get("/api/history/{session_id}")
async def get_history_detail(session_id: int, user=Depends(get_current_user)):
    detail = db.get_session_detail(session_id)
    if not detail:
        raise HTTPException(404, "Session not found")
    if detail["user_id"] != user["user_id"]:
        raise HTTPException(403, "Not your session")
    return detail


class FollowUpRequest(BaseModel):
    question: str
    answer: str
    part: int = 3

@app.post("/api/follow-up")
async def generate_follow_up(body: FollowUpRequest, user=Depends(get_current_user)):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        prompt = (
            f"You are an IELTS Speaking examiner conducting Part 3.\n"
            f"The candidate was asked: \"{body.question}\"\n"
            f"They answered: \"{body.answer}\"\n\n"
            "Generate ONE natural follow-up question that:\n"
            "- Digs deeper into the topic\n"
            "- Is appropriate for IELTS Part 3 discussion\n"
            "- Encourages the candidate to elaborate or give opinions\n\n"
            "Return ONLY the follow-up question text, nothing else."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an IELTS examiner. Return only the follow-up question."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7,
        )
        follow_up = response.choices[0].message.content.strip()
        return {"follow_up_question": follow_up}
    except Exception as e:
        logger.error(f"Follow-up error: {e}")
        raise HTTPException(500, "Failed to generate follow-up question")


class SampleAnswerRequest(BaseModel):
    question: str
    part: int = 1

@app.post("/api/sample-answer")
async def generate_sample_answer(body: SampleAnswerRequest, user=Depends(get_current_user)):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        prompt = (
            f"You are an IELTS Speaking expert. Generate a Band 7+ sample answer for this IELTS Part {body.part} question:\n\n"
            f"Question: {body.question}\n\n"
            "Requirements:\n"
            "- Use natural, fluent English\n"
            "- Include advanced vocabulary and collocations\n"
            "- Use a range of grammatical structures\n"
            "- Keep it concise but well-developed\n"
            f"- {'2-3 sentences' if body.part == 1 else '1-2 minutes of speech' if body.part == 2 else '3-5 sentences'}\n\n"
            "Return ONLY the sample answer text, no labels or headers."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an IELTS Speaking expert. Provide only the sample answer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7,
        )
        sample = response.choices[0].message.content.strip()
        return {"sample_answer": sample}
    except Exception as e:
        logger.error(f"Sample answer error: {e}")
        raise HTTPException(500, "Failed to generate sample answer")


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
    avg_score = db.get_average_score(user["user_id"])
    settings = db.get_user_settings(user["user_id"])
    return {
        "streak": streak,
        "total_sessions": total_sessions,
        "total_hours": total_hours,
        "average_score": avg_score,
        "target_score": settings.get("target_score", 6.5),
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
    voice: str = "sarah"

@app.post("/api/tts")
async def text_to_speech(body: TTSRequest, user=Depends(get_current_user)):
    import edge_tts

    if len(body.text) > 500:
        raise HTTPException(400, "Text too long")

    voice = EDGE_TTS_VOICES.get(body.voice, EDGE_TTS_VOICES["sarah"])

    try:
        communicate = edge_tts.Communicate(body.text, voice)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            raise HTTPException(502, "TTS generation failed")

        audio_data = b"".join(audio_chunks)
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Edge TTS error: {e}")
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
