"""
Language middleware.

After the auth middleware has resolved the platform user, this middleware:
  1. Reads the user's preferred language from the User object.
  2. Creates a bound Translator for that language and stores it in context.
  3. Caches the language in LanguageService for fast subsequent lookups.

Usage:
    # Registered in main.py as a TypeHandler at group=-1 (after auth).
    from telegram.ext import TypeHandler, Update
    application.add_handler(
        TypeHandler(Update, language_middleware_handler), group=-1
    )

After this runs, handlers can access the translator via:
    from locales.translator import Translator
    tr: Translator = context.user_data.get("translator")
    text = tr.get("welcome.greeting", name="Alice")

Phase 0.4: Full implementation.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.middlewares.auth import PLATFORM_USER_KEY, TRANSLATOR_KEY
from app.observability import request_ctx

logger = logging.getLogger(__name__)


async def language_middleware_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Attach a language-bound Translator to the current update context.

    No-ops when:
      • The update has no effective user.
      • The auth middleware has not yet resolved the platform user.
    """
    user = context.user_data.get(PLATFORM_USER_KEY)
    if user is None:
        return  # Auth middleware either not run yet or user not found.

    lang = user.language.value if user.language else "en"
    request = request_ctx.get()
    if request is not None:
        request.language = lang

    # Build a Translator bound to the user's language.
    from locales.translator import Translator
    translator = Translator(lang)
    context.user_data[TRANSLATOR_KEY] = translator

    # Populate LanguageService cache so hot-path translate() calls are fast.
    language_service = context.bot_data.get("language_service")
    if language_service is not None:
        language_service.cache_language(user.telegram_id, lang)

    logger.debug(
        "language_middleware: language=%s telegram_id=%s",
        lang, user.telegram_id,
    )
