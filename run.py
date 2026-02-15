"""
Run both the Telegram bot and FastAPI web server together.
Whisper model is loaded once and shared between them.
"""
import os
import sys
import asyncio
import logging
import threading

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
    """Run the Telegram bot."""
    logger.info("Starting Telegram bot...")
    # Import and run the existing bot
    # We need to patch app.py to not run on import
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "app.py")
    app_module = importlib.util.module_from_spec(spec)

    # Prevent app.py from executing main on import
    original_name = "__main__"
    app_module.__name__ = "app_module"

    spec.loader.exec_module(app_module)
    await app_module.main()


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
