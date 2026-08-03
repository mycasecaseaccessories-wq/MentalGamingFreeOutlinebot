"""
Activity middleware.

Updates the last_active timestamp for the current user on every incoming
update.  Runs after the auth middleware has resolved the platform user.

Design notes:
  • Fire-and-forget: failures are logged but never raise to the caller,
    so a DB hiccup does not disrupt the user's interaction.
  • Uses UserService.update_last_active() which issues a direct UPDATE
    (no SELECT round-trip) for minimal latency overhead.

Usage:
    # Registered in main.py as a TypeHandler at group=-1 (after auth and language).
    from telegram.ext import TypeHandler, Update
    application.add_handler(
        TypeHandler(Update, activity_middleware_handler), group=-1
    )

Phase 0.4: Full implementation.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.middlewares.auth import PLATFORM_USER_KEY

logger = logging.getLogger(__name__)


async def activity_middleware_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Stamp last_active for the current user in the background.

    No-ops when:
      • The update has no effective user.
      • The auth middleware has not resolved the platform user.
      • UserService is not available in bot_data.
    """
    user = context.user_data.get(PLATFORM_USER_KEY)
    if user is None:
        return

    user_service = context.bot_data.get("user_service")
    if user_service is None:
        return

    try:
        await user_service.update_last_active(user.telegram_id)
    except Exception as exc:
        # Activity tracking is non-critical — never surface to the user.
        logger.warning(
            "activity_middleware: failed to update last_active for telegram_id=%s — %s",
            user.telegram_id, exc,
        )
