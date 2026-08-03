"""
Logging middleware.

Records every incoming Telegram update at DEBUG level.
Useful for audit trails and debugging during development.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def logging_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Log metadata about the incoming update.

    Logs at DEBUG level to avoid polluting INFO output in production.
    Never logs message text content to protect user privacy.
    """
    user = update.effective_user
    chat = update.effective_chat

    logger.debug(
        "update received — update_id=%s user_id=%s username=%s chat_id=%s chat_type=%s",
        update.update_id,
        user.id if user else "n/a",
        user.username if user else "n/a",
        chat.id if chat else "n/a",
        chat.type if chat else "n/a",
    )
