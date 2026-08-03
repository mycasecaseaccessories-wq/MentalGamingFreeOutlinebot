"""
Mental Outline VPN Platform — application entry point.

Startup sequence:
  1. Initialise logging (must be first).
  2. Load and validate settings from environment.
  3. Initialise the database (run Alembic migrations to HEAD).
  4. Seed default settings and feature flags (SettingsService.seed_defaults).
  5. Build the Telegram Application.
  6. Register handlers (start, admin, error).
  7. Start the scheduler.
  8. Run the bot (polling).

To add a new handler group:
  - Create app/handlers/my_feature.py with register(application).
  - Import and call it below in the "Register handlers" section.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure the bot/ directory is on sys.path when running as `python main.py`
# from inside the bot/ folder or from the repo root.
sys.path.insert(0, str(Path(__file__).parent))

# ── 1. Logging must be set up before any module that uses logging is imported.
from app.utils.logger import setup_logging  # noqa: E402


async def main() -> None:
    """Async application bootstrap."""
    # ── 2. Settings ────────────────────────────────────────────────────────
    from config import settings  # imported here so setup_logging runs first

    setup_logging(level=settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting Mental Outline VPN Platform — env=%s language=%s",
        settings.environment,
        settings.default_language,
    )

    # ── 3. Database ────────────────────────────────────────────────────────
    from database import DatabaseManager

    db = DatabaseManager.initialise(settings.database_url)
    await db.init()
    logger.info("Database ready — url=%s", settings.database_url.split("://")[0])

    # ── 4. Settings seed ───────────────────────────────────────────────────
    # Insert default settings and feature flags that are missing from the DB.
    # Safe to call on every startup — existing rows are never overwritten.
    from app.services import SettingsService

    await SettingsService(db).seed_defaults()
    logger.info("Settings seed complete.")

    # ── 5. Build Telegram Application ─────────────────────────────────────
    from telegram.ext import Application

    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )

    # ── 6. Register handlers ───────────────────────────────────────────────
    from app.handlers import register_start, register_admin, register_error

    register_start(application)
    register_admin(application)
    register_error(application)   # Error handler must be last.
    logger.info("All handlers registered.")

    # ── 7. Scheduler ──────────────────────────────────────────────────────
    from app.scheduler import Scheduler

    scheduler = Scheduler()
    scheduler.register_jobs()
    scheduler.start()

    # ── 8. Run (polling) ───────────────────────────────────────────────────
    logger.info("Bot is starting — polling for updates…")
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)

        # Block until a shutdown signal is received.
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await db.close()
        logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
