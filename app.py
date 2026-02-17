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
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@MultilevelSpeaking9")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    logging.error("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY")
    raise ValueError("❌ Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY")

from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_KEY)
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
        TESTS = data.get('tests', [])
        if not TESTS:
            raise ValueError("No tests found in questions.json")
except FileNotFoundError as e:
    logging.error("questions.json not found")
    raise SystemExit(e)

# Store user states
user_states = {}

# Initialize user state
def initialize_user_state():
    if not TESTS:
        raise ValueError("No tests available")

    selected_test = random.choice(TESTS)
    parts = selected_test["parts"]

    return {
        "part": "1.1",
        "question_index": 0,
        "answers": [],
        "selected_test": selected_test,
        "selected_questions": {
            "1.1": parts["1.1"]["questions"],
            "1.2": parts["1.2"]["questions"],
            "2": parts["2"]["questions"],
            "3": []  # Part 3 is debate, handled separately
        },
        "debate_side": None,
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

    # Handle referral deep link: /start ref_XXXXXXXX
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            referral_code = arg[4:].upper()
            try:
                import db as db_module
                result = db_module.process_referral(user_id, referral_code)
                if result.get("success"):
                    await update.message.reply_text("🎉 Referral applied! You got +1 bonus mock test.")
                    logging.info(f"User {user_id} used referral code: {referral_code}")
                elif result.get("error"):
                    logging.info(f"User {user_id} referral failed: {result['error']}")
            except Exception as e:
                logging.error(f"Referral error for {user_id}: {e}")

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
                "🎤 Welcome to Multilevel Speaking Practice! Click 'Start Exam'.",
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

    await update.message.reply_text("📝 Multilevel Speaking exam started! 30 minutes to complete.")
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
        await update.message.reply_text("Start exam using /start.")
        return

    part = state["part"]
    index = state["question_index"]
    questions = state["selected_questions"].get(part, [])
    test = state["selected_test"]

    # Part flow: 1.1 -> 1.2 -> 2 -> 3
    part_order = ["1.1", "1.2", "2", "3"]

    if part == "3":
        # Debate part - show debate table and ask user to speak
        debate_data = test["parts"]["3"]
        if not state.get("debate_shown"):
            state["debate_shown"] = True
            debate_msg = (
                f"Part 3 - Debate\n\n"
                f"Topic: {debate_data['topic']}\n\n"
                f"FOR:\n" + "\n".join(f"  + {p}" for p in debate_data['for_points']) + "\n\n"
                f"AGAINST:\n" + "\n".join(f"  - {p}" for p in debate_data['against_points']) + "\n\n"
                f"Choose a side and argue your position. You have 120 seconds."
            )
            await update.message.reply_text(debate_msg)
            if audio_buffer := text_to_speech(f"The debate topic is: {debate_data['topic']}. Choose a side, for or against, and argue your position."):
                await update.message.reply_voice(voice=audio_buffer, caption="Audio for debate topic")
        else:
            # Debate response already given, end exam
            if state["timeout_task"]:
                state["timeout_task"].cancel()
            await provide_feedback(update, context)
        return

    if index < len(questions):
        question = questions[index]

        # For Part 1.2, send images before first question
        if part == "1.2" and index == 0:
            images = test["parts"]["1.2"].get("images", [])
            for img_url in images:
                try:
                    await update.message.reply_photo(photo=img_url, caption=f"Picture for Part 1.2")
                except Exception as e:
                    logging.error(f"Failed to send image: {e}")

        await update.message.reply_text(f"Part {part}, Question {index + 1}:\n{question}")

        if audio_buffer := text_to_speech(question):
            await update.message.reply_voice(
                voice=audio_buffer,
                caption=f"Audio for Question {index + 1} (Part {part})"
            )
    else:
        # Move to next part
        current_idx = part_order.index(part)
        if current_idx < len(part_order) - 1:
            state["part"] = part_order[current_idx + 1]
            state["question_index"] = 0
            await update.message.reply_text(f"Moving to Part {state['part']}...")
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

        time_limits = {"1.1": 30, "1.2": 30, "2": 60, "3": 120}
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
            if current_part == "3":
                current_question = state["selected_test"]["parts"]["3"]["topic"]
            else:
                current_question = state["selected_questions"][current_part][state["question_index"]]
            initial_prompt = {
                "1.1": f"Response to Multilevel Part 1.1 interview question: {current_question}",
                "1.2": f"Response to Multilevel Part 1.2 picture description question: {current_question}",
                "2": f"Response to Multilevel Part 2 discussion question: {current_question}",
                "3": f"Response to Multilevel Part 3 debate: {current_question}"
            }.get(current_part, f"Response to Multilevel question: {current_question}")

            logging.info(f"User {user_id}: Starting transcription at {datetime.utcnow().isoformat()}")
            with open(wav_path, "rb") as audio_file:
                result = groq_client.audio.transcriptions.create(
                    file=(wav_path, audio_file.read()),
                    model="whisper-large-v3-turbo",
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
    reached_part2 = any(answer['part'] in ["2", "1.2", "3"] for answer in answers)
    # Check for short responses (5-8 seconds)
    has_short_response = any(5 <= answer['duration'] <= 8 for answer in answers)

    if not reached_part2:
        feedback = (
            "Exam Feedback:\n"
            "Overall Score: 10/75\n"
            "CEFR Level: Below B1\n"
            "The candidate did not complete the exam, failing to progress beyond Part 1.1, which severely limits assessment. "
            "Responses provided were insufficient to demonstrate adequate language skills. "
            "Further practice and full participation are strongly recommended.\n"
            "Fluency and Coherence: 10/75\n"
            "The candidate's limited responses lacked coherence due to incomplete participation.\n"
            "Lexical Resource: 10/75\n"
            "Vocabulary could not be adequately assessed due to insufficient responses.\n"
            "Grammatical Range and Accuracy: 8/75\n"
            "Grammar was not sufficiently demonstrated due to the absence of responses beyond Part 1.1.\n"
            "Pronunciation: 10/75\n"
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
            "Exam Feedback:\n"
            "Overall Score: 10/75\n"
            "CEFR Level: Below B1\n"
            "The candidate's responses were extremely brief, lasting only 5-8 seconds, which severely limits assessment. "
            "This brevity prevented a thorough evaluation of language skills. "
            "Longer responses are needed to demonstrate proficiency.\n"
            "Fluency and Coherence: 10/75\n"
            "Responses were too short to assess fluency or coherence effectively.\n"
            "Lexical Resource: 10/75\n"
            "Limited speech duration restricted vocabulary assessment.\n"
            "Grammatical Range and Accuracy: 8/75\n"
            "Grammar was not sufficiently demonstrated due to very short responses.\n"
            "Pronunciation: 10/75\n"
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
        "You are a certified Multilevel Speaking examiner. Analyze the following responses based on:\n"
        "1. Fluency and Coherence\n2. Lexical Resource\n"
        "3. Grammatical Range and Accuracy\n4. Pronunciation\n"
        "Score each criterion on 0-75 integer scale.\n"
        "CEFR: C1(65-75), B2(51-64), B1(38-50), Below B1(0-37)\n"
        "Provide:\n"
        "- Overall Score (0-75) with CEFR level and a three-sentence summary.\n"
        "- Scores for each criterion with a one-sentence comment.\n"
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
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a certified Multilevel Speaking examiner."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        feedback = response.choices[0].message.content

        final_feedback = "Exam Feedback:\n" + feedback
        await update.message.reply_text(final_feedback, parse_mode="Markdown")

        if audio_buffer := text_to_speech(feedback):
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
    reached_part2 = any(answer['part'] in ["2", "1.2", "3"] for answer in answers)
    # Check for short responses (5-8 seconds)
    has_short_response = any(5 <= answer['duration'] <= 8 for answer in answers)

    if not reached_part2:
        feedback = (
            "Exam Feedback (Incomplete due to Timeout):\n"
            "Overall Score: 10/75\n"
            "CEFR Level: Below B1\n"
            "The candidate did not complete the exam, failing to progress beyond Part 1.1, which severely limits assessment. "
            "Responses provided were insufficient to demonstrate adequate language skills. "
            "Further practice and full participation are strongly recommended.\n"
            "Fluency and Coherence: 10/75\n"
            "The candidate's limited responses lacked coherence due to incomplete participation.\n"
            "Lexical Resource: 10/75\n"
            "Vocabulary could not be adequately assessed due to insufficient responses.\n"
            "Grammatical Range and Accuracy: 8/75\n"
            "Grammar was not sufficiently demonstrated due to the absence of responses beyond Part 1.1.\n"
            "Pronunciation: 10/75\n"
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
            "Exam Feedback (Incomplete due to Timeout):\n"
            "Overall Score: 10/75\n"
            "CEFR Level: Below B1\n"
            "The candidate's responses were extremely brief, lasting only 5-8 seconds, which severely limits assessment. "
            "This brevity prevented a thorough evaluation of language skills. "
            "Longer responses are needed to demonstrate proficiency.\n"
            "Fluency and Coherence: 10/75\n"
            "Responses were too short to assess fluency or coherence effectively.\n"
            "Lexical Resource: 10/75\n"
            "Limited speech duration restricted vocabulary assessment.\n"
            "Grammatical Range and Accuracy: 8/75\n"
            "Grammar was not sufficiently demonstrated due to very short responses.\n"
            "Pronunciation: 10/75\n"
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
        "You are a certified Multilevel Speaking examiner. Analyze the following responses based on:\n"
        "1. Fluency and Coherence\n2. Lexical Resource\n"
        "3. Grammatical Range and Accuracy\n4. Pronunciation\n"
        "Score each criterion on 0-75 integer scale.\n"
        "CEFR: C1(65-75), B2(51-64), B1(38-50), Below B1(0-37)\n"
        "Note: Exam timed out (30 minutes), so responses may be incomplete.\n"
        "Provide:\n"
        "- Overall Score (0-75) with CEFR level and a three-sentence summary, noting incomplete exam.\n"
        "- Scores for each criterion with a one-sentence comment.\n"
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
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a certified Multilevel Speaking examiner."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        feedback = response.choices[0].message.content
        final_feedback = "Exam Feedback (Incomplete due to Timeout):\n" + feedback
        await context.bot.send_message(chat_id=user_id, text=final_feedback, parse_mode="Markdown")

        if audio_buffer := text_to_speech(feedback):
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
    if not args or len(args) < 1:
        await update.message.reply_text(
            "Usage:\n"
            "/upgrade_gold <user_id>\n"
            "/upgrade_gold @username\n\n"
            "To downgrade:\n"
            "/downgrade <user_id or @username>"
        )
        return

    target = args[0]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if target.startswith("@"):
        username = target[1:]
        c.execute("SELECT user_id, first_name, tariff FROM users WHERE username = ?", (username,))
    elif target.isdigit():
        c.execute("SELECT user_id, first_name, tariff FROM users WHERE user_id = ?", (int(target),))
    else:
        await update.message.reply_text("❌ Provide user_id (number) or @username")
        conn.close()
        return

    row = c.fetchone()
    if not row:
        await update.message.reply_text(f"❌ User not found: {target}")
        conn.close()
        return

    target_user_id = row[0]
    name = row[1] or target
    old_tariff = row[2] or 'free'

    c.execute("UPDATE users SET tariff = 'gold' WHERE user_id = ?", (target_user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ User upgraded to Premium!\n\n"
        f"👤 {name} ({target_user_id})\n"
        f"📦 {old_tariff} → gold\n"
        f"🎯 Mock limit: 5/day"
    )
    logging.info(f"Admin {user_id} upgraded {target_user_id} to gold")


async def downgrade_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Not authorized.")
        return

    args = context.args
    if not args or len(args) < 1:
        await update.message.reply_text("Usage: /downgrade <user_id or @username>")
        return

    target = args[0]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if target.startswith("@"):
        username = target[1:]
        c.execute("SELECT user_id, first_name FROM users WHERE username = ?", (username,))
    elif target.isdigit():
        c.execute("SELECT user_id, first_name FROM users WHERE user_id = ?", (int(target),))
    else:
        await update.message.reply_text("❌ Provide user_id or @username")
        conn.close()
        return

    row = c.fetchone()
    if not row:
        await update.message.reply_text(f"❌ User not found: {target}")
        conn.close()
        return

    target_user_id = row[0]
    name = row[1] or target

    c.execute("UPDATE users SET tariff = 'free' WHERE user_id = ?", (target_user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ User downgraded to Free.\n\n"
        f"👤 {name} ({target_user_id})\n"
        f"📦 gold → free\n"
        f"🎯 Mock limit: 2/day"
    )
    logging.info(f"Admin {user_id} downgraded {target_user_id} to free")

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
    application.add_handler(CommandHandler("downgrade", downgrade_user))
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