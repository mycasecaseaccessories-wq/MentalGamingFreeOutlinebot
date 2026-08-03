"""
Authentication middleware.

Resolves the platform User record for every incoming update and attaches
it to context.user_data so handlers can access it without hitting the DB.

Behaviour:
  1. Extracts the Telegram user from the update.
  2. Calls UserService.register_user() (get-or-create).
  3. Stores the User in context.user_data["platform_user"].
  4. Blocks the update with an error message if the account is banned
     or suspended (can_use_bot == False).

Usage:
    # Registered in main.py as a TypeHandler at group=-1.
    from telegram.ext import TypeHandler, Update
    application.add_handler(
        TypeHandler(Update, auth_middleware_handler), group=-1
    )
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Keys used in context.user_data to share state between middleware and handlers.
PLATFORM_USER_KEY = "platform_user"
TRANSLATOR_KEY = "translator"


async def auth_middleware_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Resolve and attach the platform User to every incoming update.

    Reads DatabaseManager and UserService from context.bot_data (set in main.py).
    No-ops gracefully when update.effective_user is absent (e.g. channel posts).

    After this runs, handlers can access the user via:
        user = context.user_data.get("platform_user")
    """
    tg_user = update.effective_user
    if tg_user is None:
        return  # Channel posts and some service messages have no user.

    user_service = context.bot_data.get("user_service")
    if user_service is None:
        logger.warning("auth_middleware: user_service not found in bot_data — skipping.")
        return

    try:
        user, created = await user_service.register_user(
            telegram_id=tg_user.id,
            full_name=tg_user.full_name,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )
    except Exception as exc:
        logger.error(
            "auth_middleware: failed to register user %s — %s",
            tg_user.id, exc, exc_info=True,
        )
        return

    # Attach to context so handlers don't need to call UserService themselves.
    context.user_data[PLATFORM_USER_KEY] = user

    # Block banned or suspended accounts before any handler runs.
    if not user.can_use_bot and update.message:
        from locales.translator import t
        lang = user.language.value if user.language else "en"
        key = "auth.banned" if user.is_banned else "auth.suspended"
        await update.message.reply_text(t(key, language=lang))
        logger.info(
            "auth_middleware: blocked update for %s account — telegram_id=%s",
            user.status.value, tg_user.id,
        )
        return

    if created:
        logger.debug("auth_middleware: new user registered — telegram_id=%s", tg_user.id)
    else:
        logger.debug("auth_middleware: user resolved — telegram_id=%s", tg_user.id)
