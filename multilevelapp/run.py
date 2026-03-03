"""
Run both the Telegram bot and FastAPI web server together.
"""
import os
import sys
import asyncio
import logging
import threading
import time
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

SYNC_INTERVAL_HOURS = 2


def run_supabase_sync_loop():
    """Background thread: sync local PostgreSQL → Supabase every N hours."""
    import supabase_sync as sb
    # Wait before first sync (let the app fully start)
    time.sleep(60)
    while True:
        try:
            logger.info("Starting scheduled Supabase sync...")
            sb.full_sync_to_supabase()
            logger.info("Scheduled Supabase sync completed.")
        except Exception as e:
            logger.error(f"Scheduled Supabase sync failed: {e}")
        time.sleep(SYNC_INTERVAL_HOURS * 3600)


def run_web_server():
    """Run FastAPI server in a separate thread."""
    import uvicorn
    import web_server
    import db
    import supabase_sync as sb

    # Run migrations
    db.migrate()

    # Restore from Supabase if local DB is empty (e.g. after fresh deploy)
    sb.restore_from_supabase()

    # Start periodic Supabase backup
    sync_thread = threading.Thread(target=run_supabase_sync_loop, daemon=True, name="supabase-sync")
    sync_thread.start()
    logger.info(f"Supabase sync scheduler started (every {SYNC_INTERVAL_HOURS}h)")

    port = int(os.getenv("WEB_PORT", "8000"))
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
