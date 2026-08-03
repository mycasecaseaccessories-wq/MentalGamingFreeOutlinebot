"""
Global error handler.

Catches every unhandled exception raised inside any handler or callback
and ensures the bot never crashes silently.

Principles:
  • Log the full traceback at ERROR level.
  • Optionally notify admin users about unexpected errors in production.
  • Always send a graceful message to the user so they are not left hanging.
"""

from __future__ import annotations

import html
import logging
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from config import settings

logger = logging.getLogger(__name__)


async def global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle all unhandled exceptions raised by handlers.

    Registered last on the Application so it acts as a catch-all.
    """
    # Build a human-readable traceback string.
    tb_string = "".join(
        traceback.format_exception(
            type(context.error), context.error, context.error.__traceback__
        )
    )

    logger.error(
        "Unhandled exception in update handler.\n"
        "Update: %s\n"
        "Error: %s\n"
        "Traceback:\n%s",
        str(update),
        context.error,
        tb_string,
    )

    # Notify the user who triggered the error (best-effort).
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Our team has been notified.\n"
                "Please try again in a moment."
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send error reply to user")

    # Notify all admin users about the error (production only).
    if settings.is_production and settings.admin_ids:
        error_summary = (
            f"<b>⚠️ Bot error detected</b>\n\n"
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
                logger.exception("Failed to notify admin_id=%s", admin_id)


def register(application: Application) -> None:
    """Register the global error handler with the given Application."""
    application.add_error_handler(global_error_handler)
    logger.debug("global error handler registered")
