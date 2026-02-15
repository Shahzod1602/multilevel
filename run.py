"""
Run both the Telegram bot and FastAPI web server together.
Whisper model is loaded once and shared between them.
"""
import os
import sys
import asyncio
import logging
import threading
import runpy

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

logger = logging.getLogger(__name__)


def run_web_server():
    """Run FastAPI server in a separate thread."""
    import uvicorn
    import web_server
    import db

    # Run migrations
    db.migrate()

    # Share whisper model
    try:
        import whisper
        logger.info("Loading Whisper model...")
        web_server.whisper_model = whisper.load_model("small").to("cpu")
        logger.info("Whisper model loaded for web server")
    except Exception as e:
        logger.error(f"Failed to load Whisper model for web server: {e}")

    port = int(os.getenv("WEB_PORT", "8080"))
    logger.info(f"Starting web server on port {port}...")
    uvicorn.run(web_server.app, host="0.0.0.0", port=port, log_level="info")


async def run_bot():
    """Run the Telegram bot by importing app module and calling main()."""
    logger.info("Starting Telegram bot...")

    # Add current dir to path so app.py can be imported
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    # Import app.py as a regular module (it won't call main() because __name__ != "__main__")
    import app as bot_app
    await bot_app.main()


def main():
    # Start web server in a thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Web server thread started")

    # Run bot in main thread's event loop
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
