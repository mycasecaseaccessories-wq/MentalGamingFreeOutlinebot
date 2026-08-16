"""Phase 1.1 `/start` and onboarding handlers."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.handlers.base import log_handler
from app.keyboards.language import build_onboarding_language_keyboard
from app.middlewares.auth import PLATFORM_USER_KEY
from app.models.customer_entry import EntryDecision, EntryRoute
from app.models.enums import UserRole
from app.services.customer_entry_service import CustomerEntryService
from locales.translator import t

logger = logging.getLogger(__name__)


def _get_entry_service(context: ContextTypes.DEFAULT_TYPE) -> CustomerEntryService | None:
    service = context.bot_data.get("customer_entry_service")
    if service is not None:
        return service
    registry = context.bot_data.get("registry")
    if registry is not None:
        return registry.get_or_none(CustomerEntryService)
    return None


def _extract_start_parameter(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    if not context.args:
        return None
    return context.args[0]


@log_handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle `/start` without checking VPN key ownership."""
    message = update.effective_message
    user = context.user_data.get(PLATFORM_USER_KEY) if context.user_data is not None else None
    service = _get_entry_service(context)

    if message is None:
        return
    if user is None or service is None:
        logger.error("Phase 1.1 entry dependencies unavailable")
        await message.reply_text(t("start.error", language="en"))
        return

    raw_start_parameter = _extract_start_parameter(context)
    decision = await service.resolve(
        user=user,
        is_new_user=bool(context.user_data.pop("is_new_user", False)),
        admin_ids=context.bot_data["settings"].admin_ids,
        start_parameter=raw_start_parameter,
    )
    if decision.start_parameter and context.user_data is not None:
        context.user_data["start_parameter"] = decision.start_parameter

    await _render_entry_decision(update, context, decision)


async def _render_entry_decision(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    decision: EntryDecision,
    *,
    edit_existing: bool = False,
) -> None:
    """Render a transport decision. Full customer navigation starts in Phase 1.2."""
    lang = decision.language if decision.language in {"en", "my"} else "en"
    message = update.effective_message
    query = update.callback_query

    if decision.route == EntryRoute.LANGUAGE_SELECTION:
        name = update.effective_user.first_name if update.effective_user else ""
        text = t("start.welcome_first", language="en", name=name or "there")
        text += "\n\n" + t("language.select_bilingual", language="en")
        markup = build_onboarding_language_keyboard()
        if edit_existing and query is not None:
            await query.edit_message_text(text, reply_markup=markup)
        elif message is not None:
            await message.reply_text(text, reply_markup=markup)
        return

    if decision.route == EntryRoute.ACCESS_RESTRICTED:
        text = t(decision.restriction_key or "start.access_restricted", language=lang)
        if edit_existing and query is not None:
            await query.edit_message_text(text)
        elif message is not None:
            await message.reply_text(text)
        return

    if decision.route == EntryRoute.ADMIN:
        text = t("start.admin_placeholder", language=lang)
        if edit_existing and query is not None:
            await query.edit_message_text(text)
        elif message is not None:
            await message.reply_text(text)
        return

    if decision.route == EntryRoute.CUSTOMER:
        # Phase 1.2: real customer main menu. Keep admin routing separate.
        from app.handlers.customer_navigation import show_customer_main_menu
        await show_customer_main_menu(update, context, first_entry=decision.is_new_user)
        return

    text = t(
        "start.future_role_placeholder",
        language=lang,
        role=decision.role.value,
    )
    if edit_existing and query is not None:
        await query.edit_message_text(text)
    elif message is not None:
        await message.reply_text(text)


async def language_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Persist explicit language selection and route without another `/start`."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user = context.user_data.get(PLATFORM_USER_KEY) if context.user_data is not None else None
    service = _get_entry_service(context)
    if user is None or service is None:
        await query.edit_message_text(t("start.error", language="en"))
        return

    parts = (query.data or "").split(":")
    language_code = parts[-1] if len(parts) == 3 else "en"

    try:
        decision = await service.select_language(user, language_code)
    except ValueError:
        logger.warning("Invalid onboarding language callback: %r", query.data)
        await query.answer(t("error.language_required", language="en"), show_alert=True)
        return

    # Keep middleware-shared domain object synchronized for this update.
    user.language = type(user.language)(language_code)
    if context.user_data is not None:
        context.user_data[PLATFORM_USER_KEY] = user

    logger.info(
        "Phase 1.1 language selected — telegram_id=%s language=%s",
        user.telegram_id,
        language_code,
    )
    confirmation = t("welcome.lang_saved", language=language_code)
    if decision.role == UserRole.ADMIN:
        await query.edit_message_text(
            f"{confirmation}\n\n"
            f"{t('start.admin_placeholder', language=language_code)}"
        )
        return

    await query.edit_message_text(confirmation)
    from app.handlers.customer_navigation import show_customer_main_menu
    await show_customer_main_menu(update, context, first_entry=True)


@log_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Phase 1.1 help placeholder."""
    user = context.user_data.get(PLATFORM_USER_KEY) if context.user_data is not None else None
    lang = user.language.value if user and user.language else "en"
    if update.effective_message:
        await update.effective_message.reply_text(t("placeholder.coming_soon", language=lang))


def register(application: Application) -> None:
    """Register Phase 1.1 start/onboarding handlers."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        CallbackQueryHandler(
            language_selection_callback,
            pattern=r"^onboarding:lang:(en|my)$",
        )
    )
    logger.debug("Phase 1.1 start handlers registered")
