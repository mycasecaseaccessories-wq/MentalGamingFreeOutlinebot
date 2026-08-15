"""
Start / help handler.

Handles the very first interaction a user has with the bot.

Phase 0.4 behaviour:
  • User is registered (or fetched) by the auth middleware before this runs.
  • New users are shown the language selection keyboard.
  • Returning users receive a role-aware welcome message.
  • A CallbackQueryHandler picks up the language selection choice.

Phase 1 behaviour:
  • Show the full main menu keyboard after language is confirmed.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from app.handlers.base import log_handler
from app.keyboards.customer_account import build_customer_menu
from app.keyboards.language import build_onboarding_language_keyboard
from app.models.customer_entry import EntryRoute
from app.models.enums import UserRole
from app.middlewares.auth import PLATFORM_USER_KEY, TRANSLATOR_KEY
from app.services.customer_entry_service import CustomerEntryService
from locales.translator import t

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /start command
# ---------------------------------------------------------------------------

@log_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.

    The auth middleware has already registered or fetched the platform user
    and stored it in context.user_data["platform_user"].
    """
    user = context.user_data.get(PLATFORM_USER_KEY)
    if user is None:
        # Fallback: auth middleware did not run or failed.
        await update.message.reply_text(
            "👋 Welcome to Mental Outline VPN!\n\n"
            "🚧 The platform is being set up. Please try again shortly."
        )
        return

    service = context.bot_data.get("customer_entry_service")
    if service is None or update.effective_message is None:
        return
    settings = context.bot_data.get("settings")
    decision = await service.resolve(
        user=user,
        is_new_user=bool(context.user_data.pop("is_new_user", False)),
        admin_ids=getattr(settings, "admin_ids", []),
        start_parameter=(context.args[0] if context.args else None),
    )
    if decision.route == EntryRoute.LANGUAGE_SELECTION:
        await update.effective_message.reply_text(
            t("welcome.choose_lang", language="en"),
            reply_markup=build_onboarding_language_keyboard(),
        )
        return
    lang = decision.language
    if decision.route == EntryRoute.ADMIN:
        await update.effective_message.reply_text(
            f"👋 {t('role.admin', language=lang)}\n\n🛠 Admin Panel",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🛠 Admin Panel", callback_data="menu:admin")]]
            ),
        )
        return
    await update.effective_message.reply_text(
        t("welcome.greeting_back", language=lang, name=user.first_name or user.full_name),
        reply_markup=build_customer_menu(lang),
    )


async def _show_language_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Send the language-selection keyboard to a new user."""
    keyboard = build_onboarding_language_keyboard()
    tg_user = update.effective_user
    name = tg_user.first_name or tg_user.full_name if tg_user else "there"

    # Bilingual prompt so the user understands regardless of their language.
    await update.message.reply_text(
        f"👋 {name}!\n\n"
        + t("welcome.choose_lang", language="en"),
        reply_markup=keyboard,
    )


# ---------------------------------------------------------------------------
# Language selection callback
# ---------------------------------------------------------------------------

async def language_selection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline-button language selection (callback_data = 'set_lang:<code>').

    Persists the chosen language for the user and sends a confirmation.
    """
    query = update.callback_query
    await query.answer()  # Acknowledge the button tap.

    parts = query.data.split(":") if query.data else []
    lang_code = parts[-1] if parts and parts[-1] in {"en", "my"} else "en"

    # Save to DB via LanguageService.
    language_service = context.bot_data.get("language_service")
    user = context.user_data.get(PLATFORM_USER_KEY)

    if language_service is not None and user is not None:
        try:
            await language_service.set_language(user.telegram_id, lang_code)
            # Update the in-context user object so downstream handlers see
            # the new language without a DB round-trip.
            from app.models.enums import Language
            user.language = Language(lang_code)
            preference_service = context.bot_data.get("preference_service")
            if preference_service is not None:
                await preference_service.set_preferences(
                    user.telegram_id,
                    {"language": lang_code, "language_selected": True},
                )
        except Exception as exc:
            logger.error("language_selection_callback: %s", exc)

    # Confirm with a message in the selected language.
    key = "welcome.lang_saved"
    await query.edit_message_text(
        t(key, language=lang_code) + "\n\n" + t("welcome.setup_complete", language=lang_code)
    )
    if user is not None:
        await query.message.reply_text(
            t("welcome.greeting_back", language=lang_code, name=user.first_name or user.full_name),
            reply_markup=build_customer_menu(lang_code),
        )
    logger.info(
        "language_selection_callback: language=%s telegram_id=%s",
        lang_code,
        user.telegram_id if user else "unknown",
    )


# ---------------------------------------------------------------------------
# /help command
# ---------------------------------------------------------------------------

@log_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /help command.

    Phase 0.4 behaviour: display a placeholder message.
    Phase 1 behaviour:   show contextual help based on the user's role.
    """
    user = context.user_data.get(PLATFORM_USER_KEY)
    lang = user.language.value if user and user.language else "en"
    await update.message.reply_text(t("placeholder.coming_soon", language=lang))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(application: Application) -> None:
    """Register all handlers in this module with the given Application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        CallbackQueryHandler(language_selection_callback, pattern=r"^(set_lang|onboarding:language):")
    )
    logger.debug("start handlers registered")
