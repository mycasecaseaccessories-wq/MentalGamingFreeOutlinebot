"""
Request logging middleware.

Logs every incoming Telegram update at DEBUG level with the user's
Telegram ID, update type, and a short summary of the payload.

This gives a complete audit trail of user interactions without any
business-logic coupling.  Sensitive message text is truncated to 100
chars to avoid flooding the log with large payloads.

Registration (in Bootstrap / main.py):
    application.add_handler(
        TypeHandler(Update, logging_middleware_handler), group=-1
    )

Note: Register AFTER auth/language/activity middlewares so the resolved
      platform user is already in context when this logs.

Phase 0.5: Full implementation.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.middlewares.auth import PLATFORM_USER_KEY

logger = logging.getLogger("bot.requests")

_MAX_TEXT_LEN = 100  # Truncate message text to this many chars in logs.


def _update_summary(update: Update) -> str:
    """Return a short human-readable summary of the update payload."""
    if update.message:
        text = update.message.text or update.message.caption or ""
        truncated = text[:_MAX_TEXT_LEN] + ("…" if len(text) > _MAX_TEXT_LEN else "")
        return f"message: {truncated!r}"
    if update.callback_query:
        return f"callback_query: data={update.callback_query.data!r}"
    if update.inline_query:
        return f"inline_query: query={update.inline_query.query!r}"
    if update.edited_message:
        return "edited_message"
    if update.channel_post:
        return "channel_post"
    return f"update_id={update.update_id}"


async def logging_middleware_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Log every incoming update at DEBUG level.

    Logs:
      • Telegram user ID and username (from update.effective_user).
      • Platform user role and status (from context.user_data, if resolved).
      • Update type and payload summary.

    Never raises — logging failures are swallowed so a broken log
    destination never disrupts the bot.
    """
    try:
        tg_user = update.effective_user
        if tg_user is None:
            logger.debug("incoming update (no effective_user) — %s", _update_summary(update))
            return

        platform_user = context.user_data.get(PLATFORM_USER_KEY)
        role_info = (
            f" role={platform_user.role.value} status={platform_user.status.value}"
            if platform_user else ""
        )

        logger.debug(
            "→ update from user_id=%s @%s%s — %s",
            tg_user.id,
            tg_user.username or "(no username)",
            role_info,
            _update_summary(update),
        )
    except Exception as exc:
        # Never let logging blow up the middleware chain.
        logger.warning("logging_middleware: unexpected error — %s", exc)
