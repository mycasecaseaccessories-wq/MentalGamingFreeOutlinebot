"""
Global error handler.

Catches every unhandled exception raised inside any handler or callback
and ensures the bot never crashes silently.

Error classification
--------------------
  TelegramError         — network / API errors from python-telegram-bot.
  SQLAlchemyError       — database errors (query failure, connection lost, …).
  ValidationError       — Pydantic config validation errors.
  SchedulerError        — APScheduler job errors.
  StartupError          — caught during bootstrap, logged before bot starts.
  Exception (catch-all) — any other unhandled exception.

Principles
----------
  • Log the full traceback at ERROR level with request_id when available.
  • Notify admin users in production (best-effort, never raises).
  • Always send a graceful reply to the user so they are not left hanging.
  • Never crash the application.
"""

from __future__ import annotations

import html
import logging
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error classification helpers
# ---------------------------------------------------------------------------

def _classify_error(error: BaseException) -> str:
    """Return a short category string for *error*."""
    class_name = type(error).__name__

    # Telegram API / network errors
    try:
        if isinstance(error, TelegramError):
            return "telegram"
    except Exception:
        pass

    # Database errors (SQLAlchemy)
    try:
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(error, SQLAlchemyError):
            return "database"
    except ImportError:
        pass

    # Pydantic validation / config errors
    try:
        from pydantic import ValidationError
        if isinstance(error, ValidationError):
            return "configuration"
    except ImportError:
        pass

    # APScheduler errors
    try:
        from apscheduler.schedulers.base import SchedulerNotRunningError
        if isinstance(error, SchedulerNotRunningError):
            return "scheduler"
    except ImportError:
        pass

    # Startup errors
    try:
        from app.utils.startup_checks import StartupError
        if isinstance(error, StartupError):
            return "startup"
    except ImportError:
        pass

    return "unhandled"


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

async def global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle all unhandled exceptions raised by handlers.

    Registered last on the Application so it acts as a catch-all.
    Never raises — any failure in the handler itself is caught and logged.
    """
    error = context.error
    category = _classify_error(error) if error else "unknown"

    # Resolve request_id for structured logging.
    request_id = "-"
    try:
        from app.observability import get_request_id
        request_id = get_request_id() or "-"
    except Exception:
        pass

    # Build traceback string.
    if error:
        tb_string = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    else:
        tb_string = "(no traceback)"

    logger.error(
        "[%s] Unhandled %s exception in update handler.\n"
        "Update: %s\n"
        "Error: %s\n"
        "Traceback:\n%s",
        request_id,
        category,
        str(update),
        error,
        tb_string,
    )

    # Track error metric.
    try:
        from app.observability import metrics
        metrics.increment("bot.errors.total")
        metrics.increment(f"bot.errors.{category}")
    except Exception:
        pass

    # Notify the user who triggered the error (best-effort).
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Our team has been notified.\n"
                "Please try again in a moment."
            )
        except Exception:  # noqa: BLE001
            logger.exception("[%s] Failed to send error reply to user", request_id)

    # Notify all admin users about the error (production only).
    if settings.is_production and settings.admin_ids and error:
        error_summary = (
            f"<b>⚠️ [{category.upper()}] Bot error detected</b>\n"
            f"<i>request_id: {request_id}</i>\n\n"
            f"<code>{html.escape(tb_string[-2000:])}</code>"
        )
        for admin_id in settings.admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=error_summary,
                    parse_mode=ParseMode.HTML,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "[%s] Failed to notify admin_id=%s", request_id, admin_id
                )


def register(application: Application) -> None:
    """Register the global error handler with the given Application."""
    application.add_error_handler(global_error_handler)
    logger.debug("Global error handler registered")
