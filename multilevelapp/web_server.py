"""
FastAPI backend for Multilevel Speaking Practice Telegram Mini App.
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

import aiohttp
import db

logger = logging.getLogger(__name__)

app = FastAPI(title="Multilevel Speaking Practice")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@MultilevelSpeaking9")
EDGE_TTS_VOICES = {
    "sarah": "en-US-JennyNeural",
    "lily": "en-GB-SoniaNeural",
    "charlie": "en-US-ChristopherNeural",
    "roger": "en-GB-RyanNeural",
}

# Load questions
TESTS = []
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        TESTS = data.get("tests", [])
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
    target_level: Optional[str] = None


class SessionStart(BaseModel):
    type: str = "practice"
    part: str = "1.1"
    topic: Optional[str] = None
    test_id: Optional[int] = None


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
    if body.target_level is not None:
        updates["target_level"] = body.target_level

    if updates:
        db.update_user_settings(user["user_id"], **updates)

    return db.get_user_settings(user["user_id"])


@app.get("/api/questions")
async def get_questions(part: str = "1.1", test_id: int = None, user=Depends(get_current_user)):
    if test_id is not None:
        test = next((t for t in TESTS if t["test_id"] == test_id), None)
        if not test:
            return {"questions": [], "total": 0}
        part_data = test["parts"].get(part, {})
        return {"questions": part_data.get("questions", []), "part_data": part_data, "total": len(part_data.get("questions", []))}
    # Return questions from all tests for this part
    all_questions = []
    for t in TESTS:
        part_data = t["parts"].get(part, {})
        for q in part_data.get("questions", []):
            all_questions.append(q)
    return {"questions": all_questions, "total": len(all_questions)}


@app.get("/api/tests")
async def get_tests(user=Depends(get_current_user)):
    tests_list = [{"test_id": t["test_id"], "name": t["name"]} for t in TESTS]
    return {"tests": tests_list, "total": len(tests_list)}


@app.get("/api/session-info")
async def session_info(user=Depends(get_current_user)):
    limits = db.get_user_limits(user["user_id"])
    return {
        "plan": limits["plan"],
        "status": limits["status"],
        "mock_used": limits["mock_used"],
        "mock_limit": limits["mock_limit"],
        "mock_remaining": limits["mock_remaining"],
        "practice_used": limits["practice_used"],
        "practice_limit": limits["practice_limit"],
        "practice_remaining": limits["practice_remaining"],
        "bonus_mocks": limits["bonus_mocks"],
        "days_left": limits["days_left"],
        "is_premium": limits["plan"] != "free",
        "tariff": limits["plan"],
    }


@app.get("/api/topics")
async def get_topics(part: str = "1.1", user=Depends(get_current_user)):
    topics = []
    for t in TESTS:
        part_data = t["parts"].get(part, {})
        if part_data.get("type") == "debate":
            topics.append(part_data.get("topic", ""))
        else:
            topics.append(t["name"])
    return {"topics": topics, "total": len(topics)}


CARD_NUMBER = "5614 6819 1914 7144"
CARD_HOLDER = "Nematov Shahzod"

@app.post("/api/sessions/start")
async def start_session(body: SessionStart, user=Depends(get_current_user)):
    if body.type == "mock":
        allowed = db.increment_mock_usage(user["user_id"])
        if not allowed:
            limits = db.get_user_limits(user["user_id"])
            if limits["plan"] == "free":
                raise HTTPException(403, f"Mock test limit reached ({limits['mock_limit']} total). Upgrade to Premium for more!")
            else:
                raise HTTPException(403, f"Mock test limit reached ({limits['mock_limit']} for your {limits['plan']} plan).")
    elif body.type == "practice":
        allowed = db.increment_practice_usage(user["user_id"])
        if not allowed:
            limits = db.get_user_limits(user["user_id"])
            if limits["plan"] == "free":
                raise HTTPException(403, f"Practice limit reached ({limits['practice_limit']} total). Upgrade to Premium for more!")
            else:
                raise HTTPException(403, f"Practice limit reached ({limits['practice_limit']} for your {limits['plan']} plan).")

    session_id = db.create_session(user["user_id"], body.type, body.part)

    import random
    if body.type == "mock" and body.test_id:
        # Pick specific test
        test = next((t for t in TESTS if t["test_id"] == body.test_id), None)
        if test:
            return {"session_id": session_id, "test": test}
    elif body.type == "mock":
        # Pick random test
        if TESTS:
            test = random.choice(TESTS)
            return {"session_id": session_id, "test": test}

    # Practice mode - pick questions for specific part
    part = body.part
    all_questions = []
    for t in TESTS:
        part_data = t["parts"].get(part, {})
        qs = part_data.get("questions", [])
        all_questions.extend(qs)

    if part == "3":
        # For debate, pick a random test's debate data
        if TESTS:
            test = random.choice(TESTS)
            return {"session_id": session_id, "part_data": test["parts"].get("3", {})}

    if part == "1.2":
        # For picture description, pick a random test's 1.2 data (images + questions together)
        if TESTS:
            test = random.choice(TESTS)
            pd = test["parts"].get("1.2", {})
            return {"session_id": session_id, "questions": pd.get("questions", []), "images": pd.get("images", [])}

    questions = random.sample(all_questions, min(3, len(all_questions))) if all_questions else []
    return {"session_id": session_id, "questions": questions}


@app.post("/api/sessions/{session_id}/respond")
async def session_respond(
    session_id: int,
    audio: UploadFile = File(...),
    question: str = Form(""),
    part: str = Form("1.1"),
    debate_side: str = Form(""),
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
                model="whisper-large-v3-turbo",
                language="en",
                prompt=f"Multilevel Speaking Part {part} response to: {question}",
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
        "beginner": "Be encouraging and lenient. Focus on what the learner did well. Most responses should score 20-40.",
        "intermediate": "Apply standard scoring criteria fairly. Most responses should score 35-55.",
        "advanced": "Be strict. Expect sophisticated vocabulary, complex grammar, natural fluency. Only give 55+ for truly excellent performance.",
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
        f"You are a certified Multilevel speaking examiner.\n"
        f"{level_text}\n\n"
        f"{mood_section}"
        "Analyze the following responses.\n"
        "Score each criterion on a 0-75 INTEGER scale:\n"
        "1. Fluency and Coherence\n2. Lexical Resource\n"
        "3. Grammatical Range and Accuracy\n4. Pronunciation\n\n"
        "CEFR mapping: C1(65-75), B2(51-64), B1(38-50), Below B1(0-37)\n\n"
        "Return ONLY valid JSON (no markdown, no code fences) in this format:\n"
        '{"fluency": 55, "lexical": 50, "grammar": 48, "pronunciation": 52, '
        '"overall": 51, "feedback": "Your detailed feedback here.", '
        '"cefr_level": "B2", '
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
                {"role": "system", "content": "You are a certified Multilevel speaking examiner. Return only valid JSON."},
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

        cefr_level = scores_data.get("cefr_level", db.score_to_cefr(scores.get("overall", 0)))
        return {
            "scores": scores,
            "feedback": feedback,
            "cefr_level": cefr_level,
            "grammar_corrections": grammar_corrections,
            "pronunciation_issues": pronunciation_issues,
        }

    except json.JSONDecodeError:
        # If GPT didn't return valid JSON, provide default scores
        scores = {"fluency": 40, "lexical": 40, "grammar": 38, "pronunciation": 40, "overall": 40}
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
            f"You are a Multilevel Speaking examiner conducting Part 3.\n"
            f"The candidate was asked: \"{body.question}\"\n"
            f"They answered: \"{body.answer}\"\n\n"
            "Generate ONE natural follow-up question that:\n"
            "- Digs deeper into the topic\n"
            "- Is appropriate for Multilevel Part 3 discussion\n"
            "- Encourages the candidate to elaborate or give opinions\n\n"
            "Return ONLY the follow-up question text, nothing else."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Multilevel examiner. Return only the follow-up question."},
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
            f"You are a Multilevel Speaking expert. Generate a Score 60+ sample answer for this Multilevel Part {body.part} question:\n\n"
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
                {"role": "system", "content": "You are a Multilevel Speaking expert. Provide only the sample answer."},
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
    cefr_level = db.score_to_cefr(avg_score) if avg_score else None
    return {
        "streak": streak,
        "total_sessions": total_sessions,
        "total_hours": total_hours,
        "average_score": avg_score,
        "target_score": settings.get("target_score", 6.5),
        "target_level": settings.get("target_level", "B2"),
        "cefr_level": cefr_level,
    }


# ─── Leaderboard ─────────────────────────────────────────────

@app.get("/api/leaderboard")
async def leaderboard(user=Depends(get_current_user)):
    lb = db.get_leaderboard(limit=20, min_sessions=3)
    user_id = user["user_id"]
    rank_data = db.get_user_rank(user_id, min_sessions=3)

    # Mark if user is in list
    for item in lb:
        item["is_me"] = item["user_id"] == user_id

    return {
        "leaderboard": lb,
        "my_rank": rank_data["rank"] if rank_data else None,
        "my_avg_score": rank_data["avg_score"] if rank_data else None,
        "my_sessions": rank_data["sessions"] if rank_data else 0,
    }


# ─── Vocabulary ──────────────────────────────────────────────

@app.get("/api/content/vocabulary")
async def get_vocabulary(user=Depends(get_current_user)):
    return {
        "categories": [
            {
                "title": "Part 1.1 — Interview Phrases",
                "description": "Natural expressions for personal questions",
                "items": [
                    {"phrase": "To be honest...", "example": "To be honest, I'm not really a morning person."},
                    {"phrase": "I'd say that...", "example": "I'd say that my favourite hobby is reading."},
                    {"phrase": "It depends on...", "example": "It depends on the situation, but usually I prefer..."},
                    {"phrase": "I'm quite keen on...", "example": "I'm quite keen on photography these days."},
                    {"phrase": "As far as I know...", "example": "As far as I know, it's the most popular sport in my country."},
                    {"phrase": "I tend to...", "example": "I tend to go for walks in the evening rather than the morning."},
                ]
            },
            {
                "title": "Part 1.2 — Describing Pictures",
                "description": "Useful language for picture description and comparison",
                "items": [
                    {"phrase": "In the foreground/background...", "example": "In the foreground, I can see a group of people having lunch."},
                    {"phrase": "It appears that...", "example": "It appears that they are enjoying a family gathering."},
                    {"phrase": "The main difference is...", "example": "The main difference between the two pictures is the setting."},
                    {"phrase": "While the first picture shows...", "example": "While the first picture shows an indoor scene, the second is outdoors."},
                    {"phrase": "I would personally prefer...", "example": "I would personally prefer the situation in the second picture."},
                    {"phrase": "What strikes me is...", "example": "What strikes me is how relaxed everyone looks."},
                ]
            },
            {
                "title": "Part 2 — Discussion Phrases",
                "description": "Extended response language for deeper discussions",
                "items": [
                    {"phrase": "From my perspective...", "example": "From my perspective, education is the key to success."},
                    {"phrase": "There are several reasons for this...", "example": "There are several reasons for this, the main one being..."},
                    {"phrase": "On the other hand...", "example": "On the other hand, some people might argue that..."},
                    {"phrase": "For instance...", "example": "For instance, in my country, most students prefer..."},
                    {"phrase": "This is largely because...", "example": "This is largely because of the influence of social media."},
                    {"phrase": "It's worth mentioning that...", "example": "It's worth mentioning that technology has changed this."},
                ]
            },
            {
                "title": "Part 3 — Debate Phrases",
                "description": "Persuasive language for arguing your position",
                "items": [
                    {"phrase": "I firmly believe that...", "example": "I firmly believe that education should be free for everyone."},
                    {"phrase": "The evidence suggests...", "example": "The evidence suggests that banning phones improves focus."},
                    {"phrase": "One could argue that...", "example": "One could argue that this approach is too extreme."},
                    {"phrase": "Furthermore...", "example": "Furthermore, studies have shown that regular exercise..."},
                    {"phrase": "In conclusion...", "example": "In conclusion, the benefits clearly outweigh the drawbacks."},
                    {"phrase": "A compelling argument is...", "example": "A compelling argument is that it promotes equality."},
                ]
            }
        ]
    }


# ─── Pronunciation Drills ────────────────────────────────────

@app.get("/api/content/pronunciation-drills")
async def get_pronunciation_drills(user=Depends(get_current_user)):
    return {
        "drills": [
            {
                "title": "Difficult Sounds",
                "items": [
                    {"word": "think", "phonetic": "/θɪŋk/", "tip": "Place tongue between teeth and blow air"},
                    {"word": "this", "phonetic": "/ðɪs/", "tip": "Tongue between teeth, add voice"},
                    {"word": "right", "phonetic": "/raɪt/", "tip": "Curl tongue back, don't touch the roof"},
                    {"word": "world", "phonetic": "/wɜːrld/", "tip": "Round lips for /w/, then curl for /r/"},
                    {"word": "very", "phonetic": "/ˈveri/", "tip": "Upper teeth on lower lip, voice it"},
                    {"word": "comfortable", "phonetic": "/ˈkʌmftəbl/", "tip": "Three syllables: KUMF-tuh-bl"},
                    {"word": "February", "phonetic": "/ˈfebrueri/", "tip": "Don't skip the first R: FEB-roo-eri"},
                    {"word": "particularly", "phonetic": "/pəˈtɪkjʊləli/", "tip": "par-TIK-yoo-luh-lee"},
                ]
            },
            {
                "title": "Common Phrases",
                "items": [
                    {"word": "as a matter of fact", "phonetic": "", "tip": "Link words smoothly: az-uh-matter-uv-fact"},
                    {"word": "in my opinion", "phonetic": "", "tip": "Natural stress on 'pin': in-my-uh-PIN-yun"},
                    {"word": "on the other hand", "phonetic": "", "tip": "Link 'the other': on-thee-OTHER-hand"},
                    {"word": "I couldn't agree more", "phonetic": "", "tip": "COULD-nt with a soft T"},
                    {"word": "it goes without saying", "phonetic": "", "tip": "Smooth linking: it-GOES-without-SAY-ing"},
                    {"word": "to a certain extent", "phonetic": "", "tip": "SER-tin, not cer-TAIN"},
                ]
            },
            {
                "title": "Minimal Pairs",
                "items": [
                    {"word": "ship vs sheep", "phonetic": "/ʃɪp/ vs /ʃiːp/", "tip": "Short /ɪ/ vs long /iː/"},
                    {"word": "bat vs bet", "phonetic": "/bæt/ vs /bet/", "tip": "Open /æ/ vs mid /e/"},
                    {"word": "light vs right", "phonetic": "/laɪt/ vs /raɪt/", "tip": "/l/ tongue touches roof, /r/ doesn't"},
                    {"word": "vest vs west", "phonetic": "/vest/ vs /west/", "tip": "/v/ teeth on lip, /w/ round lips"},
                    {"word": "sink vs think", "phonetic": "/sɪŋk/ vs /θɪŋk/", "tip": "/s/ behind teeth, /θ/ between teeth"},
                    {"word": "fan vs van", "phonetic": "/fæn/ vs /væn/", "tip": "/f/ is voiceless, /v/ is voiced"},
                ]
            }
        ]
    }


@app.post("/api/pronunciation/check")
async def check_pronunciation(
    audio: UploadFile = File(...),
    target: str = Form(""),
    user=Depends(get_current_user),
):
    """Transcribe audio and compare with target word/phrase."""
    audio_data = await audio.read()
    if len(audio_data) < 500:
        raise HTTPException(400, "Audio too short")

    ct = (audio.content_type or "").lower()
    ext_map = {
        "audio/webm": ".webm", "audio/ogg": ".ogg",
        "audio/mp4": ".m4a", "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
    }
    ext = ext_map.get(ct.split(";")[0], ".ogg")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_data)
        tmp.flush()
        audio_path = tmp.name

    wav_path = audio_path + ".wav"

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        use_path = wav_path if os.path.exists(wav_path) else audio_path

        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)

        with open(use_path, "rb") as f:
            result = groq_client.audio.transcriptions.create(
                file=(use_path, f.read()),
                model="whisper-large-v3-turbo",
                language="en",
                prompt=f"Pronunciation practice: {target}",
            )
        transcription = result.text.strip()

        # Simple similarity scoring
        target_clean = target.lower().strip().replace("vs ", "").replace("vs. ", "")
        heard_clean = transcription.lower().strip()

        # Calculate word-level match
        target_words = set(target_clean.split())
        heard_words = set(heard_clean.split())

        if target_words:
            matches = len(target_words & heard_words)
            score = min(100, int((matches / len(target_words)) * 100))
        else:
            score = 50 if transcription else 0

        # Boost score if close match
        if heard_clean == target_clean:
            score = 100
        elif target_clean in heard_clean or heard_clean in target_clean:
            score = max(score, 80)

        feedback = ""
        if score >= 90:
            feedback = "Excellent pronunciation!"
        elif score >= 70:
            feedback = "Good job! Minor differences detected."
        elif score >= 50:
            feedback = "Keep practicing. Try to match the target more closely."
        else:
            feedback = "Try listening again and repeat more slowly."

        return {
            "transcription": transcription,
            "score": score,
            "feedback": feedback,
        }
    finally:
        for f in [audio_path, wav_path]:
            try:
                os.remove(f)
            except OSError:
                pass


# ─── Admin Auth ──────────────────────────────────────────────

async def get_admin_user(request: Request) -> dict:
    """Dependency: validate user is admin."""
    user = await get_current_user(request)
    if not db.is_admin(user["user_id"]):
        raise HTTPException(403, "Admin access required")
    return user


# ─── Subscription System ─────────────────────────────────────

@app.get("/api/subscription")
async def get_subscription(user=Depends(get_current_user)):
    limits = db.get_user_limits(user["user_id"])
    return limits


class SubscriptionRequest(BaseModel):
    plan: str


@app.post("/api/subscription/request")
async def request_subscription(body: SubscriptionRequest, user=Depends(get_current_user)):
    if body.plan not in db.PLANS:
        raise HTTPException(400, "Invalid plan. Choose 'weekly' or 'monthly'.")
    result = db.create_subscription_request(user["user_id"], body.plan)
    if "error" in result:
        raise HTTPException(400, result["error"])
    plan_info = db.PLANS[body.plan]
    return {
        "success": True,
        "subscription_id": result["subscription_id"],
        "card_number": CARD_NUMBER,
        "card_holder": CARD_HOLDER,
        "amount": plan_info["amount"],
        "plan": body.plan,
    }


@app.get("/api/admin/subscriptions")
async def admin_subscriptions(user=Depends(get_admin_user)):
    pending = db.get_pending_subscriptions()
    return {"subscriptions": pending}


class SubActionRequest(BaseModel):
    action: str  # 'approve' or 'reject'


@app.put("/api/admin/subscriptions/{sub_id}")
async def admin_sub_action(sub_id: int, body: SubActionRequest, user=Depends(get_admin_user)):
    if body.action == "approve":
        result = db.approve_subscription(sub_id, user["user_id"])
    elif body.action == "reject":
        result = db.reject_subscription(sub_id)
    else:
        raise HTTPException(400, "Invalid action")
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ─── Admin Panel ─────────────────────────────────────────────

@app.get("/api/admin/stats")
async def admin_stats(user=Depends(get_admin_user)):
    return db.get_admin_stats()


@app.get("/api/admin/users")
async def admin_users(q: str = "", user=Depends(get_admin_user)):
    if not q:
        users = db.search_users("", limit=20)
    else:
        users = db.search_users(q, limit=20)
    return {"users": users}


class TariffUpdate(BaseModel):
    tariff: str = "free"

@app.put("/api/admin/users/{target_id}/tariff")
async def admin_update_tariff(target_id: int, body: TariffUpdate, user=Depends(get_admin_user)):
    if body.tariff not in ("free", "gold"):
        raise HTTPException(400, "Invalid tariff")
    db.update_user_tariff(target_id, body.tariff)
    return {"success": True, "user_id": target_id, "tariff": body.tariff}


# ─── Referral System ─────────────────────────────────────────

@app.get("/api/referral")
async def get_referral(user=Depends(get_current_user)):
    code = db.generate_referral_code(user["user_id"])
    stats = db.get_referral_stats(user["user_id"])
    return {
        "code": code,
        "referral_count": stats["referral_count"],
        "bonus_mocks": stats["bonus_mocks"],
    }


class ReferralApply(BaseModel):
    code: str

@app.post("/api/referral/apply")
async def apply_referral(body: ReferralApply, user=Depends(get_current_user)):
    result = db.process_referral(user["user_id"], body.code.strip().upper())
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"success": True, "message": "Referral applied! You got +1 bonus mock test."}


# ─── Channel Subscription Check ──────────────────────────────

@app.get("/api/check-subscription")
async def check_subscription(user=Depends(get_current_user)):
    """Check if the user is subscribed to the required Telegram channel."""
    user_id = user["user_id"]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
    params = {"chat_id": CHANNEL_USERNAME, "user_id": user_id}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()

        if data.get("ok"):
            status = data["result"]["status"]
            subscribed = status in ("member", "administrator", "creator")
        else:
            # If bot can't check (not admin in channel, etc.), assume not subscribed
            logger.warning(f"Subscription check failed for {user_id}: {data}")
            subscribed = False
    except Exception as e:
        logger.error(f"Subscription check error for {user_id}: {e}")
        subscribed = False

    channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    return {"subscribed": subscribed, "channel_url": channel_url}


@app.get("/api/content/tips")
async def get_tips(user=Depends(get_current_user)):
    return {
        "tips": [
            {"title": "Part 1.1: Interview", "content": "Answer in 2-3 sentences. Be yourself and speak naturally. Each question has 30 seconds.", "icon": "chat"},
            {"title": "Part 1.2: Pictures", "content": "Describe what you see clearly. Compare the images and give your opinion. 30 seconds per question.", "icon": "image"},
            {"title": "Part 2: Discussion", "content": "Give developed answers with examples and explanations. You have 60 seconds per question.", "icon": "lightbulb"},
            {"title": "Part 3: Debate", "content": "Choose a side (For or Against) and argue your position convincingly. You have 120 seconds.", "icon": "scale"},
            {"title": "Vocabulary: Topic Words", "content": "Learn vocabulary by topic (education, technology, environment). Use collocations naturally.", "icon": "book"},
            {"title": "Grammar: Mix it Up", "content": "Use a range of structures: conditionals, passive voice, relative clauses. Accuracy matters more than complexity.", "icon": "check"},
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
