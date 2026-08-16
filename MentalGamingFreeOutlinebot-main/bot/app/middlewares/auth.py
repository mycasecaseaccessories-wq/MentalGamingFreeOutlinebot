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
from telegram.ext import ApplicationHandlerStop, ContextTypes

from app.observability import request_ctx

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
        registry = context.bot_data.get("registry")
        if registry is not None:
            from app.services.user_service import UserService
            user_service = registry.get_or_none(UserService)
    if user_service is None:
        logger.warning("auth_middleware: user_service not available — skipping.")
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
    context.user_data["is_new_user"] = created
    request = request_ctx.get()
    if request is not None:
        request.current_user = user
        request.user_id = user.telegram_id
        request.username = user.username or user.full_name
        request.current_role = user.role.value

    # For /start, let CustomerEntryService produce the localized routing
    # decision. Other updates are stopped here so restricted accounts cannot
    # reach feature handlers.
    is_start = bool(
        update.message
        and update.message.text
        and update.message.text.split(maxsplit=1)[0].split("@", 1)[0] == "/start"
    )
    if not user.can_use_bot and not is_start:
        from locales.translator import t
        lang = user.language.value if user.language else "en"
        key = "auth.banned" if user.is_banned else "auth.suspended"
        if update.message:
            await update.message.reply_text(t(key, language=lang))
        elif update.callback_query:
            await update.callback_query.answer(t(key, language=lang), show_alert=True)
        logger.info(
            "auth_middleware: blocked update for %s account — telegram_id=%s",
            user.status.value, tg_user.id,
        )
        raise ApplicationHandlerStop

    if created:
        logger.debug("auth_middleware: new user registered — telegram_id=%s", tg_user.id)
    else:
        logger.debug("auth_middleware: user resolved — telegram_id=%s", tg_user.id)
