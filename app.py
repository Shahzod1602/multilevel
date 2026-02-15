# Import required libraries
import json
import aiohttp
import io
import os
import asyncio
import sys
import logging
import random
import sqlite3
import tempfile
import subprocess
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import openai
from gtts import gTTS
from groq import Groq
import re
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global for bot username
BOT_USERNAME = None

# Configure logging
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set event loop policy for Windows compatibility
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load credentials from .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@IELTSPEAK_bot")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    logging.error("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY")
    raise ValueError("❌ Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY")

openai.api_key = OPENAI_KEY
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_KEY)

# Database configuration
DB_NAME = "bot.db"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
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
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (5471121432,))

    # Add indexes for faster stats queries
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attempts_attempt_time ON attempts(attempt_time)")

    try:
        with open('questions.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'users' in data:
                for user in data['users']:
                    user_id = user.get('user_id')
                    contact = user.get('contact')
                    tariff = user.get('tariff', 'free')
                    if user_id and contact:
                        c.execute("INSERT OR REPLACE INTO users (user_id, contact, tariff) VALUES (?, ?, ?)",
                                  (user_id, contact, tariff))
                        logging.info(f"Saved user {user_id} from questions.json")
    except Exception as e:
        logging.error(f"Error loading users from questions.json: {str(e)}")

    conn.commit()
    conn.close()

init_db()

# Load questions
try:
    with open('questions.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        QUESTIONS = data if isinstance(data, list) else data.get('questions', [])
        if not QUESTIONS:
            raise ValueError("❌ No questions found in questions.json")
except FileNotFoundError as e:
    logging.error("questions.json not found")
    raise SystemExit(e)

# Store user states
user_states = {}

# Group questions by theme
def group_questions_by_related_to(questions):
    grouped = {}
    for question in questions:
        related_to = question.get('related_to', 'default')
        if related_to not in grouped:
            grouped[related_to] = {'part1': [], 'part2': [], 'part3': []}
        part = question.get('part')
        if part == 1:
            grouped[related_to]['part1'].append(question)
        elif part == 2:
            grouped[related_to]['part2'].append(question)
        elif part == 3:
            grouped[related_to]['part3'].append(question)
    return grouped

# Initialize user state
def initialize_user_state():
    grouped_questions = group_questions_by_related_to(QUESTIONS)
    available_groups = [g for g in grouped_questions if grouped_questions[g]['part2'] and grouped_questions[g]['part3']]
    if not available_groups:
        raise ValueError("❌ No valid groups with Part 2 and Part 3 questions")

    all_part1_questions = [q for q in QUESTIONS if q.get('part') == 1]
    if not all_part1_questions:
        raise ValueError("❌ No Part 1 questions")

    selected_group = random.choice(available_groups)
    part2_questions = grouped_questions[selected_group]['part2']
    part3_questions = grouped_questions[selected_group]['part3']

    return {
        "part": 1,
        "question_index": 0,
        "answers": [],
        "selected_questions": {
            1: random.sample(all_part1_questions, min(5, len(all_part1_questions))),
            2: [random.choice(part2_questions)] if part2_questions else [],
            3: random.sample(part3_questions, min(4, len(part3_questions))) if part3_questions else []
        },
        "selected_group": selected_group,
        "start_time": datetime.utcnow(),
        "timeout_task": None
    }

# Convert text to speech
def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer
    except Exception as e:
        logging.error(f"Error generating audio: {str(e)}")
        return None

# Get user tariff
def get_user_tariff(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT tariff FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'free'

# Count user attempts
def count_attempts(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    one_day_ago = datetime.utcnow() - timedelta(hours=24)
    c.execute("SELECT COUNT(*) FROM attempts WHERE user_id = ? AND attempt_time > ?",
              (user_id, one_day_ago))
    count = c.fetchone()[0]
    conn.close()
    return count

# Add an attempt
def add_attempt(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO attempts (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# Check if user is admin
def is_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return bool(result)

# Save response to JSON
async def save_response_to_file(user_id, response_data):
    filename = f"user_{user_id}_responses.json"
    try:
        data = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data.append(response_data)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Response saved for user {user_id}")
    except Exception as e:
        logging.error(f"Error saving response for user {user_id}: {str(e)}")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT contact FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if not user:
        keyboard = [[KeyboardButton("Share Contact", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "📋 Please share your contact.",
            reply_markup=reply_markup
        )
    else:
        # After contact, check subscription
        await check_subscription(update, context)
    logging.info(f"User {user_id} started bot")

# Handle contact
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    contact = update.message.contact
    phone_number = contact.phone_number

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, contact, tariff) VALUES (?, ?, ?)",
              (user_id, phone_number, 'free'))
    conn.commit()
    conn.close()

    # After saving contact, check subscription
    await check_subscription(update, context)
    logging.info(f"User {user_id} shared contact: {phone_number}")

# Check subscription to channel
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.message.from_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            # Subscribed, show Start Exam
            keyboard = [[KeyboardButton("Start Exam")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.effective_message.reply_text(
                "🎤 Welcome to IELTS Speaking Practice! Click 'Start Exam'.",
                reply_markup=reply_markup
            )
            # Also show Open App button if WEBAPP_URL is set
            if WEBAPP_URL:
                inline_kb = [[InlineKeyboardButton(
                    "📱 Open App",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )]]
                await update.effective_message.reply_text(
                    "Or open the full practice app:",
                    reply_markup=InlineKeyboardMarkup(inline_kb)
                )
        else:
            # Not subscribed, prompt to subscribe
            await show_subscription_prompt(update, context)
    except Exception as e:
        logging.error(f"Subscription check error for {user_id}: {str(e)}")
        # Instead of error message, show subscription prompt
        await show_subscription_prompt(update, context)

# Helper to show subscription prompt
async def show_subscription_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_USERNAME
    if BOT_USERNAME is None:
        # Fallback if not set
        BOT_USERNAME = "Romantic_chatbot"  # Replace with actual bot username if needed
    start_url =  f"https://t.me/{BOT_USERNAME}?start=1"
    inline_keyboard = [
        [InlineKeyboardButton("Join channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("Check Subscription", url=start_url)]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)
    await update.effective_message.reply_text(
        "📢 Please join our channel to proceed!\n\nAfter joining, click 'Check Subscription' to continue.",
        reply_markup=reply_markup
    )

# Handle exam timeout
async def timeout_exam(user_id, context: ContextTypes.DEFAULT_TYPE):
    if user_id in user_states:
        await context.bot.send_message(
            chat_id=user_id,
            text="⏰ Time's up! Exam ended (30 minutes exceeded)."
        )
        await provide_feedback_for_timeout(user_id, context)
        logging.info(f"Exam timed out for user {user_id}")

# Start exam
async def start_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT contact FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if not user:
        await update.message.reply_text("❌ Share contact using /start.")
        return

    # Re-check subscription before starting exam
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            await show_subscription_prompt(update, context)
            return
    except Exception as e:
        logging.error(f"Subscription check error for {user_id}: {str(e)}")
        await show_subscription_prompt(update, context)
        return

    tariff = get_user_tariff(user_id)
    attempts = count_attempts(user_id)
    max_attempts = 5 if tariff == 'gold' else 2

    if attempts >= max_attempts:
        await update.message.reply_text(
            f"❌ Limit reached: {max_attempts} tests/24h for {tariff} tariff."
        )
        logging.info(f"User {user_id} exceeded {tariff} limit: {attempts}/{max_attempts}")
        return

    user_states[user_id] = initialize_user_state()
    add_attempt(user_id)

    filename = f"user_{user_id}_responses.json"
    if os.path.exists(filename):
        os.remove(filename)
        logging.info(f"Cleared response file for user {user_id}")

    timeout_task = asyncio.create_task(asyncio.sleep(1800))
    user_states[user_id]["timeout_task"] = timeout_task
    asyncio.create_task(timeout_exam_after_sleep(user_id, context, timeout_task))

    await update.message.reply_text("📝 IELTS Speaking exam started! 30 minutes to complete.")
    await send_next_question(update, context)
    logging.info(f"User {user_id} started exam (Attempt {attempts + 1}/{max_attempts})")

# Timeout helper
async def timeout_exam_after_sleep(user_id, context, timeout_task):
    await timeout_task
    await timeout_exam(user_id, context)

# Send next question
async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)

    if not state:
        await update.message.reply_text("❌ Start exam using /start.")
        return

    part = state["part"]
    index = state["question_index"]
    questions = state["selected_questions"].get(part, [])

    if not questions:
        await update.message.reply_text(f"❌ No questions for Part {part}.")
        return

    if index < len(questions):
        question = questions[index]['question']
        await update.message.reply_text(f"📋 Part {part}, Question {index + 1}:\n{question}")

        if audio_buffer := text_to_speech(question):
            await update.message.reply_voice(
                voice=audio_buffer,
                caption=f"🎧 Audio for Question {index + 1} (Part {part})"
            )

        if part == 2:
            await update.message.reply_text("⏱️ 1 minute to prepare, 1-2 minutes to speak.")
    else:
        if part < 3:
            state["part"] += 1
            state["question_index"] = 0
            await update.message.reply_text(f"➡️ Moving to Part {state['part']}...")
            await send_next_question(update, context)
        else:
            if state["timeout_task"]:
                state["timeout_task"].cancel()
            await provide_feedback(update, context)

# Handle voice responses
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)

    if not state:
        await update.message.reply_text("❌ Start exam first.")
        return

    start_time = datetime.utcnow()
    logging.info(f"User {user_id}: Start processing voice response at {start_time.isoformat()}")

    try:
        voice = update.message.voice
        duration = voice.duration
        current_part = state["part"]

        time_limits = {1: 30, 2: 120, 3: 60}
        allowed_time = time_limits[current_part]

        if duration < 5:
            await update.message.reply_text("⚠️ Too short. Record at least 5 seconds.")
            logging.warning(f"User {user_id} response too short ({duration}s) for Part {current_part}")
            return

        if duration > allowed_time:
            await update.message.reply_text(
                f"⚠️ Part {current_part} limit: {allowed_time}s. You spoke for {duration}s."
            )

        logging.info(f"User {user_id}: Downloading voice file at {datetime.utcnow().isoformat()}")
        voice_file = await update.message.voice.get_file()
        async with aiohttp.ClientSession() as session:
            async with session.get(voice_file.file_path) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP error {resp.status}")
                audio_data = await resp.read()
        logging.info(f"User {user_id}: Voice file downloaded at {datetime.utcnow().isoformat()}")

        audio_size = len(audio_data)
        if audio_size < 10000:
            await update.message.reply_text("⚠️ Volume too low. Speak louder.")
            logging.warning(f"User {user_id} audio size too small ({audio_size} bytes)")
            return

        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
            temp_ogg.write(audio_data)
            temp_ogg.flush()
            ogg_path = temp_ogg.name

        wav_path = ogg_path.replace('.ogg', '.wav')
        logging.info(f"User {user_id}: Starting FFmpeg conversion at {datetime.utcnow().isoformat()}")
        try:
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', ogg_path, '-af', 'afftdn=nf=-25', wav_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                raise Exception(f"FFmpeg error: {result.stderr}")
        except Exception as e:
            logging.error(f"FFmpeg error for user {user_id}: {str(e)}")
            os.remove(ogg_path)
            await update.message.reply_text("❌ Failed to process audio.")
            return
        logging.info(f"User {user_id}: FFmpeg conversion completed at {datetime.utcnow().isoformat()}")

        try:
            current_question = state["selected_questions"][current_part][state["question_index"]]['question']
            initial_prompt = {
                1: f"Response to IELTS Part 1 question: {current_question}",
                2: f"Response to IELTS Part 2 question, likely in Tashkent, Uzbekistan: {current_question}",
                3: f"Response to IELTS Part 3 question: {current_question}"
            }.get(current_part, f"Response to IELTS question: {current_question}")

            logging.info(f"User {user_id}: Starting transcription at {datetime.utcnow().isoformat()}")
            with open(wav_path, "rb") as audio_file:
                result = groq_client.audio.transcriptions.create(
                    file=(wav_path, audio_file.read()),
                    model="distil-whisper-large-v3-en",
                    language="en",
                    prompt=initial_prompt,
                )
            transcription = result.text.strip()
            transcription = (
                transcription.replace("CD center", "city center")
                .replace("store card", "stone arch")
                .replace("Pakistan", "Uzbekistan")
                .replace("I someone", "someone")
                .replace("business shit", "business-savvy")
                .replace("cleans", "clients")
                .replace("letter", "later")
                .replace("they’re trusted", "they’re not trusted")
                .replace("do some early on", "do the same regarding")
                .replace("rippler", "regularly")
                .replace("cants", "can’t")
                .replace("a kind of a spender", "a special gift")
            )
            if not transcription:
                raise Exception("Transcription empty")
            logging.info(f"User {user_id}: Transcription completed at {datetime.utcnow().isoformat()}")
            logging.info(
                f"User {user_id} response (Part {current_part}, Q{state['question_index'] + 1}): {transcription}")
        except Exception as e:
            logging.error(f"Whisper error for user {user_id}: {str(e)}")
            await update.message.reply_text("❌ Failed to transcribe. Record clearly.")
            return
        finally:
            try:
                os.remove(ogg_path)
                os.remove(wav_path)
            except Exception:
                pass

        response_data = {
            "part": current_part,
            "question": current_question,
            "transcription": transcription,
            "duration": duration,
            "limit": allowed_time,
            "exceeded": duration > allowed_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        logging.info(f"User {user_id}: Saving response to file at {datetime.utcnow().isoformat()}")
        await save_response_to_file(user_id, response_data)

        state["answers"].append(response_data)
        state["question_index"] += 1
        logging.info(f"User {user_id}: Sending next question at {datetime.utcnow().isoformat()}")
        await send_next_question(update, context)

        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        logging.info(f"User {user_id}: Voice response processed in {processing_time:.2f} seconds")

    except Exception as e:
        logging.error(f"Voice processing error for user {user_id}: {str(e)}")
        await update.message.reply_text("❌ Failed to process response.")

# Adjust IELTS scores
def adjust_score(score):
    try:
        score = float(score)
        if 0 <= score <= 3.5:
            return score
        elif 3.5 < score <= 6:
            return min(score + 0.5, 9)
        else:
            return score
    except (ValueError, TypeError):
        return score

# Adjust feedback scores
def adjust_feedback_scores(feedback_text, user_id):
    # Extract criterion scores
    criteria = {
        'Fluency and Coherence': None,
        'Lexical Resource': None,
        'Grammatical Range and Accuracy': None,
        'Pronunciation': None
    }
    for criterion in criteria:
        match = re.search(rf'{criterion}: (\d+\.?\d?)', feedback_text)
        if match:
            criteria[criterion] = float(match.group(1))

    # Adjust criterion scores
    for criterion in criteria:
        if criteria[criterion] is not None:
            adjusted = adjust_score(criteria[criterion])
            logging.info(f"User {user_id}: Adjusting {criterion} from {criteria[criterion]} to {adjusted}")
            criteria[criterion] = adjusted

    # Enforce Grammar 0.5 or 1 lower than Lexical Resource
    if criteria['Lexical Resource'] is not None and criteria['Grammatical Range and Accuracy'] is not None:
        lexical = criteria['Lexical Resource']
        grammar = criteria['Grammatical Range and Accuracy']
        if grammar >= lexical:
            new_grammar = max(lexical - 1, lexical - 0.5)
            logging.info(
                f"User {user_id}: Adjusting Grammar from {grammar} to {new_grammar} to be 0.5/1 below Lexical {lexical}")
            criteria['Grammatical Range and Accuracy'] = new_grammar

    # Calculate Overall Band Score as arithmetic mean, rounded to nearest 0.5
    if all(score is not None for score in criteria.values()):
        overall_score = sum(criteria.values()) / 4
        overall_score = round(overall_score * 2) / 2  # Round to nearest 0.5
        overall_score = min(max(overall_score, 0), 9)  # Cap between 0 and 9
        logging.info(f"User {user_id}: Calculated Overall Band Score: {overall_score}")
    else:
        overall_score = None
        logging.warning(f"User {user_id}: Could not calculate Overall Band Score due to missing criterion scores")

    # Replace scores in feedback text
    for criterion, score in criteria.items():
        if score is not None:
            score_str = f"{score:.1f}" if score % 1 != 0 else f"{int(score)}"
            feedback_text = re.sub(rf'{criterion}: \d+\.?\d?', f'{criterion}: {score_str}', feedback_text)

    if overall_score is not None:
        overall_str = f"{overall_score:.1f}" if overall_score % 1 != 0 else f"{int(overall_score)}"
        feedback_text = re.sub(r'Overall Band Score: \d+\.?\d?', f'Overall Band Score: {overall_str}', feedback_text)

    return feedback_text

# Generate feedback
async def provide_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    filename = f"user_{user_id}_responses.json"

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            answers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading responses for user {user_id}: {str(e)}")
        await update.message.reply_text("❌ No answers found.")
        if user_id in user_states:
            del user_states[user_id]
        return

    if not answers:
        await update.message.reply_text("❌ No answers found.")
        if user_id in user_states:
            del user_states[user_id]
        return

    # Check for incomplete test (no Part 2 or beyond)
    reached_part2 = any(answer['part'] >= 2 for answer in answers)
    # Check for short responses (5-8 seconds)
    has_short_response = any(5 <= answer['duration'] <= 8 for answer in answers)

    if not reached_part2:
        feedback = (
            "📊 **Exam Feedback:**\n"
            "Overall Band Score: 1.5\n"
            "The candidate did not complete the exam, failing to progress beyond Part 1, which severely limits assessment. "
            "Responses provided were insufficient to demonstrate adequate language skills. "
            "Further practice and full participation are strongly recommended.\n"
            "Fluency and Coherence: 1.5\n"
            "The candidate’s limited responses lacked coherence due to incomplete participation.\n"
            "Lexical Resource: 1.5\n"
            "Vocabulary could not be adequately assessed due to insufficient responses.\n"
            "Grammatical Range and Accuracy: 1.0\n"
            "Grammar was not sufficiently demonstrated due to the absence of responses beyond Part 1.\n"
            "Pronunciation: 1.5\n"
            "Pronunciation was not adequately assessable due to limited speech input."
        )
        logging.info(f"User {user_id}: Low scores assigned due to incomplete test (no Part 2)")
        await update.message.reply_text(feedback, parse_mode="Markdown")
        if audio_buffer := text_to_speech(feedback):
            await update.message.reply_voice(voice=audio_buffer, caption="🎧 Audio feedback")
        os.remove(filename)
        if user_id in user_states:
            del user_states[user_id]
        logging.info(f"Feedback generated, file deleted for user {user_id}")
        return

    if has_short_response:
        feedback = (
            "📊 **Exam Feedback:**\n"
            "Overall Band Score: 1.5\n"
            "The candidate’s responses were extremely brief, lasting only 5-8 seconds, which severely limits assessment. "
            "This brevity prevented a thorough evaluation of language skills. "
            "Longer responses are needed to demonstrate proficiency.\n"
            "Fluency and Coherence: 1.5\n"
            "Responses were too short to assess fluency or coherence effectively.\n"
            "Lexical Resource: 1.5\n"
            "Limited speech duration restricted vocabulary assessment.\n"
            "Grammatical Range and Accuracy: 1.0\n"
            "Grammar was not sufficiently demonstrated due to very short responses.\n"
            "Pronunciation: 1.5\n"
            "Pronunciation was minimally assessable due to brief responses."
        )
        logging.info(f"User {user_id}: Low scores assigned due to short responses (5-8s)")
        await update.message.reply_text(feedback, parse_mode="Markdown")
        if audio_buffer := text_to_speech(feedback):
            await update.message.reply_voice(voice=audio_buffer, caption="🎧 Audio feedback")
        os.remove(filename)
        if user_id in user_states:
            del user_states[user_id]
        logging.info(f"Feedback generated, file deleted for user {user_id}")
        return

    prompt = (
        "You are a certified IELTS Speaking examiner. Analyze the following responses based on:\n"
        "1. Fluency and Coherence: Assess logical flow and idea connection, penalizing major disruptions.\n"
        "2. Lexical Resource: Evaluate vocabulary appropriateness, rewarding topic-specific terms.\n"
        "3. Grammatical Range and Accuracy: Prioritize detecting major grammatical errors (e.g., verb forms, sentence fragments); score 0.5 or 1 point lower than Lexical Resource.\n"
        "4. Pronunciation: Judge based on transcription clarity, noting accent-related errors.\n"
        "Provide:\n"
        "- Overall Band Score (0-9, half-points) with a three-sentence comment summarizing performance.\n"
        "- One set of scores (0-9, half-points) for Fluency and Coherence, Lexical Resource, Grammatical Range and Accuracy, and Pronunciation, each with a one-sentence comment.\n"
        "Scores 0-3.5 should reflect true performance, 3.5-7 should be generous (add points), capped at 9.\n"
        "Consider duration only if too short (Part 1: <10s, Part 2: <30s, Part 3: <15s) or too long (Part 1: >30s, Part 2: >120s, Part 3: >60s).\n"
        "Responses:\n"
    )

    for answer in answers:
        prompt += (
            f"\nPart {answer['part']} (Duration: {answer['duration']}/{answer['limit']}s):\n"
            f"Question: {answer['question']}\n"
            f"Transcription: {answer['transcription']}\n"
            f"{'Time limit exceeded' if answer['exceeded'] else ''}\n"
        )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a certified IELTS Speaking examiner."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        feedback = response.choices[0].message['content']
        adjusted_feedback = adjust_feedback_scores(feedback, user_id)

        final_feedback = "📊 **Exam Feedback:**\n" + adjusted_feedback
        await update.message.reply_text(final_feedback, parse_mode="Markdown")

        if audio_buffer := text_to_speech(adjusted_feedback):
            await update.message.reply_voice(
                voice=audio_buffer,
                caption="🎧 Audio feedback"
            )

        os.remove(filename)
        logging.info(f"Feedback generated, file deleted for user {user_id}")

    except Exception as e:
        logging.error(f"Feedback error for user {user_id}: {str(e)}")
        await update.message.reply_text(f"❌ Error generating feedback: {str(e)}")
    finally:
        if user_id in user_states:
            del user_states[user_id]
            logging.info(f"Cleared state for user {user_id}")

# Timeout feedback
async def provide_feedback_for_timeout(user_id, context: ContextTypes.DEFAULT_TYPE):
    filename = f"user_{user_id}_responses.json"

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            answers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await context.bot.send_message(chat_id=user_id, text="❌ No answers provided.")
        if user_id in user_states:
            del user_states[user_id]
        return

    if not answers:
        await context.bot.send_message(chat_id=user_id, text="❌ No answers provided.")
        if user_id in user_states:
            del user_states[user_id]
        return

    # Check for incomplete test (no Part 2 or beyond)
    reached_part2 = any(answer['part'] >= 2 for answer in answers)
    # Check for short responses (5-8 seconds)
    has_short_response = any(5 <= answer['duration'] <= 8 for answer in answers)

    if not reached_part2:
        feedback = (
            "📊 **Exam Feedback (Incomplete due to Timeout):**\n"
            "Overall Band Score: 1.5\n"
            "The candidate did not complete the exam, failing to progress beyond Part 1, which severely limits assessment. "
            "Responses provided were insufficient to demonstrate adequate language skills. "
            "Further practice and full participation are strongly recommended.\n"
            "Fluency and Coherence: 1.5\n"
            "The candidate’s limited responses lacked coherence due to incomplete participation.\n"
            "Lexical Resource: 1.5\n"
            "Vocabulary could not be adequately assessed due to insufficient responses.\n"
            "Grammatical Range and Accuracy: 1.0\n"
            "Grammar was not sufficiently demonstrated due to the absence of responses beyond Part 1.\n"
            "Pronunciation: 1.5\n"
            "Pronunciation was not adequately assessable due to limited speech input."
        )
        logging.info(f"User {user_id}: Low scores assigned due to incomplete test (no Part 2, timeout)")
        await context.bot.send_message(chat_id=user_id, text=feedback, parse_mode="Markdown")
        if audio_buffer := text_to_speech(feedback):
            await context.bot.send_voice(chat_id=user_id, voice=audio_buffer, caption="🎧 Audio feedback")
        os.remove(filename)
        if user_id in user_states:
            del user_states[user_id]
        logging.info(f"Timeout feedback generated, file deleted for user {user_id}")
        return

    if has_short_response:
        feedback = (
            "📊 **Exam Feedback (Incomplete due to Timeout):**\n"
            "Overall Band Score: 1.5\n"
            "The candidate’s responses were extremely brief, lasting only 5-8 seconds, which severely limits assessment. "
            "This brevity prevented a thorough evaluation of language skills. "
            "Longer responses are needed to demonstrate proficiency.\n"
            "Fluency and Coherence: 1.5\n"
            "Responses were too short to assess fluency or coherence effectively.\n"
            "Lexical Resource: 1.5\n"
            "Limited speech duration restricted vocabulary assessment.\n"
            "Grammatical Range and Accuracy: 1.0\n"
            "Grammar was not sufficiently demonstrated due to very short responses.\n"
            "Pronunciation: 1.5\n"
            "Pronunciation was minimally assessable due to brief responses."
        )
        logging.info(f"User {user_id}: Low scores assigned due to short responses (5-8s, timeout)")
        await context.bot.send_message(chat_id=user_id, text=feedback, parse_mode="Markdown")
        if audio_buffer := text_to_speech(feedback):
            await context.bot.send_voice(chat_id=user_id, voice=audio_buffer, caption="🎧 Audio feedback")
        os.remove(filename)
        if user_id in user_states:
            del user_states[user_id]
        logging.info(f"Timeout feedback generated, file deleted for user {user_id}")
        return

    prompt = (
        "You are a certified IELTS Speaking examiner. Analyze the following responses based on:\n"
        "1. Fluency and Coherence: Assess logical flow and idea connection, penalizing major disruptions.\n"
        "2. Lexical Resource: Evaluate vocabulary appropriateness, rewarding topic-specific terms.\n"
        "3. Grammatical Range and Accuracy: Prioritize detecting major grammatical errors (e.g., verb forms, sentence fragments); score 0.5 or 1 point lower than Lexical Resource.\n"
        "4. Pronunciation: Judge based on transcription clarity, noting accent-related errors.\n"
        "Note: Exam timed out (30 minutes), so responses may be incomplete.\n"
        "Provide:\n"
        "- Overall Band Score (0-9, half-points) with a three-sentence comment summarizing performance, noting incomplete exam.\n"
        "- One set of scores (0-9, half-points) for Fluency and Coherence, Lexical Resource, Grammatical Range and Accuracy, and Pronunciation, each with a one-sentence comment.\n"
        "Scores 0-3.5 should reflect true performance, 3.5-7 should be generous (add points), capped at 9.\n"
        "Consider duration only if too short (Part 1: <10s, Part 2: <30s, Part 3: <15s) or too long (Part 1: >30s, Part 2: >120s, Part 3: >60s).\n"
        "Responses:\n"
    )

    for answer in answers:
        prompt += (
            f"\nPart {answer['part']} (Duration: {answer['duration']}/{answer['limit']}s):\n"
            f"Question: {answer['question']}\n"
            f"Transcription: {answer['transcription']}\n"
            f"{'Time limit exceeded' if answer['exceeded'] else ''}\n"
        )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a certified IELTS Speaking examiner."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        feedback = response.choices[0].message['content']
        adjusted_feedback = adjust_feedback_scores(feedback, user_id)
        final_feedback = "📊 **Exam Feedback (Incomplete due to Timeout):**\n" + adjusted_feedback
        await context.bot.send_message(chat_id=user_id, text=final_feedback, parse_mode="Markdown")

        if audio_buffer := text_to_speech(adjusted_feedback):
            await context.bot.send_voice(
                chat_id=user_id,
                voice=audio_buffer,
                caption="🎧 Audio feedback"
            )

        os.remove(filename)
        logging.info(f"Timeout feedback generated, file deleted for user {user_id}")

    except Exception as e:
        logging.error(f"Timeout feedback error for user {user_id}: {str(e)}")
        await context.bot.send_message(chat_id=user_id, text=f"❌ Error: {str(e)}")
    finally:
        if user_id in user_states:
            del user_states[user_id]
            logging.info(f"Cleared state for user {user_id}")

# Admin commands
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Not authorized.")
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: /admin_add <user_id>")
        return

    new_admin_id = int(args[0])
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ User {new_admin_id} added as admin.")
    logging.info(f"User {user_id} added admin {new_admin_id}")

async def send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Not authorized.")
        return

    message = ' '.join(context.args)
    if not message:
        await update.message.reply_text("Usage: /send_all <message>")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()

    for (target_user_id,) in users:
        try:
            await context.bot.send_message(chat_id=target_user_id, text=message)
            logging.info(f"Message sent to {target_user_id} by {user_id}")
        except Exception as e:
            logging.error(f"Failed to send message to {target_user_id}: {str(e)}")

    await update.message.reply_text("✅ Message sent to all users.")

async def upgrade_gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Not authorized.")
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: /upgrade_gold <user_id>")
        return

    target_user_id = int(args[0])
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET tariff = 'gold' WHERE user_id = ?", (target_user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ User {target_user_id} upgraded to gold.")
    logging.info(f"User {user_id} upgraded {target_user_id} to gold")

async def upload_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Not an admin.")
        return

    if not update.message.photo and not update.message.caption:
        await update.message.reply_text("📸 Send a photo with a caption.")
        return

    photo = update.message.photo[-1]
    caption = update.message.caption or "Advertisement"

    file = await photo.get_file()
    file_path = f"ads/{photo.file_id}.jpg"
    os.makedirs("ads", exist_ok=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(file.file_path) as resp:
            if resp.status == 200:
                with open(file_path, "wb") as f:
                    f.write(await resp.read())

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO ads (admin_id, image_path, caption, schedule_time) VALUES (?, ?, ?, ?)",
              (user_id, file_path, caption, datetime.utcnow() + timedelta(hours=1)))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Ad scheduled for 1 hour.")
    logging.info(f"Admin {user_id} uploaded ad: {file_path}")

async def send_ad(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, image_path, caption FROM ads WHERE sent = 0 AND schedule_time <= ?",
              (datetime.utcnow(),))
    ads = c.fetchall()

    c.execute("SELECT user_id FROM users")
    users = c.fetchall()

    for ad_id, image_path, caption in ads:
        for (user_id,) in users:
            try:
                state = user_states.get(user_id, {})
                theme = state.get("selected_group", "default")
                themed_caption = f"{caption}\n🎯 Theme: {theme}"
                with open(image_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=InputFile(photo),
                        caption=themed_caption
                    )
                logging.info(f"Ad {ad_id} sent to {user_id}")
            except Exception as e:
                logging.error(f"Failed to send ad {ad_id} to {user_id}: {str(e)}")

        c.execute("UPDATE ads SET sent = 1 WHERE id = ?", (ad_id,))
        conn.commit()

    conn.close()

# New: Admin stats command
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Not authorized.")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Total users
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    # New users today
    c.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
    new_users_today = c.fetchone()[0]

    # Users who used today (distinct attempts today)
    c.execute("SELECT COUNT(DISTINCT user_id) FROM attempts WHERE DATE(attempt_time) = DATE('now')")
    users_used_today = c.fetchone()[0]

    conn.close()

    stats_message = (
        f"📈 **Bot Statistics:**\n"
        f"- Total users: {total_users}\n"
        f"- New users today: {new_users_today}\n"
        f"- Users who used the bot today: {users_used_today}"
    )
    await update.message.reply_text(stats_message, parse_mode="Markdown")
    logging.info(f"Admin {user_id} requested stats")

# Main function
async def main():
    global BOT_USERNAME
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^Start Exam$'), start_exam))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(CommandHandler("admin_add", admin_add))
    application.add_handler(CommandHandler("send_all", send_all))
    application.add_handler(CommandHandler("upgrade_gold", upgrade_gold))
    application.add_handler(MessageHandler(filters.PHOTO, upload_ad))
    application.add_handler(CommandHandler("stats", stats))

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_ad, 'interval', seconds=60, args=[application.bot])
    scheduler.start()

    try:
        await application.initialize()
        bot_info = await application.bot.get_me()
        BOT_USERNAME = bot_info.username
        logging.info(f"Bot username set to: @{BOT_USERNAME}")
        await application.start()
        await application.updater.start_polling()
        await asyncio.Event().wait()  # Keep running until interrupted
    except Exception as e:
        logging.error(f"Application error: {str(e)}")
        raise
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())