"""
Admin handler module.

All handlers in this module are restricted to users listed in settings.admin_ids.
Business-logic commands (server management, user banning, etc.) will be
added in Phase 1+.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .base import admin_only, log_handler
from config import settings

logger = logging.getLogger(__name__)


@admin_only
@log_handler
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /admin command.

    Phase 0 behaviour: confirm admin access and show placeholder panel.
    Phase 1 behaviour: render the full admin dashboard keyboard.
    """
    user = update.effective_user

    # Temporary hard-coded admin check until middleware is wired up.
    if user.id not in settings.admin_ids:
        await update.message.reply_text("⛔ You do not have admin access.")
        logger.warning("Unauthorized /admin attempt — user_id=%s", user.id)
        return

    logger.info("admin_panel accessed — user_id=%s", user.id)

    # TODO (Phase 1): render full admin panel with inline keyboard.
    await update.message.reply_text(
        "🛠 Admin Panel\n\n"
        "Platform is in setup mode (Phase 0).\n"
        "Full admin features arrive in Phase 1."
    )


def register(application: Application) -> None:
    """Register all admin handlers with the given Application."""
    application.add_handler(CommandHandler("admin", admin_panel))
    logger.debug("admin handlers registered")
