"""
Start / help handler.

Handles the very first interaction a user has with the bot.
Business logic (user registration, subscription check, etc.) will be
wired in when the corresponding services are implemented (Phase 1+).
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .base import log_handler

logger = logging.getLogger(__name__)


@log_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.

    Phase 0 behaviour: acknowledge the user and confirm the bot is alive.
    Phase 1 behaviour: register user, detect language, show main menu.
    """
    user = update.effective_user
    logger.info("start_command — user_id=%s", user.id if user else "unknown")

    # TODO (Phase 1): call UserService.get_or_create(user) here.
    # TODO (Phase 1): send localised welcome message with main menu keyboard.
    await update.message.reply_text(
        "👋 Welcome to Mental Outline VPN Platform.\n\n"
        "🚧 The platform is being set up. Stay tuned!"
    )


@log_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command.

    Phase 0 behaviour: display a placeholder message.
    Phase 1 behaviour: show contextual help based on the user's role.
    """
    # TODO (Phase 1): build role-aware help message.
    await update.message.reply_text(
        "ℹ️ Help is coming soon. Please check back after the platform launches."
    )


def register(application: Application) -> None:
    """Register all handlers in this module with the given Application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    logger.debug("start handlers registered")
