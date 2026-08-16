"""Phase 1.2 customer main UI and navigation handlers."""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.handlers.base import log_handler
from app.keyboards.main_menu import (
    build_customer_main_menu,
    build_customer_page_navigation,
)
from app.middlewares.auth import PLATFORM_USER_KEY
from app.models.enums import UserRole
from app.models.navigation import CustomerMenuItem
from app.services.customer_navigation_service import CustomerNavigationService
from locales.translator import t

logger = logging.getLogger(__name__)

_CUSTOMER_SURFACE_ROLES = {
    UserRole.CUSTOMER,
    UserRole.VIP,
    UserRole.RESELLER,
    UserRole.AFFILIATE,
}


def _get_navigation_service(
    context: ContextTypes.DEFAULT_TYPE,
) -> CustomerNavigationService | None:
    service = context.bot_data.get("customer_navigation_service")
    if service is not None:
        return service
    registry = context.bot_data.get("registry")
    if registry is not None:
        return registry.get_or_none(CustomerNavigationService)
    return None


def _get_user(context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        return None
    return context.user_data.get(PLATFORM_USER_KEY)


def _language(user) -> str:
    try:
        value = user.language.value
    except AttributeError:
        value = getattr(user, "language", "en")
    return value if value in {"en", "my"} else "en"


def _is_customer_surface(user) -> bool:
    return bool(
        user
        and user.role in _CUSTOMER_SURFACE_ROLES
        and getattr(user, "can_use_bot", True)
    )


async def show_customer_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    first_entry: bool = False,
) -> None:
    """Render the localized persistent customer main menu."""
    user = _get_user(context)
    service = _get_navigation_service(context)
    message = update.effective_message

    if message is None or not _is_customer_surface(user):
        return

    lang = _language(user)
    if service is not None:
        await service.open_main(user.telegram_id)

    key = "menu.customer_welcome" if first_entry else "menu.customer_title"
    await message.reply_text(
        t(key, language=lang, name=user.first_name or user.full_name or ""),
        reply_markup=build_customer_main_menu(lang),
    )


@log_handler
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu and /home for customer-facing roles."""
    user = _get_user(context)
    if not _is_customer_surface(user):
        return
    await show_customer_main_menu(update, context)


async def navigation_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline navigation callbacks."""
    query = update.callback_query
    user = _get_user(context)
    if query is None or not _is_customer_surface(user):
        return

    await query.answer()
    if query.data == "nav:home":
        lang = _language(user)
        service = _get_navigation_service(context)
        if service is not None:
            await service.open_main(user.telegram_id)

        # Reply keyboards cannot be attached to editMessageText, so remove the
        # inline placeholder page and send a fresh main-menu message.
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Could not clear inline navigation markup", exc_info=True)

        if query.message is not None:
            await query.message.reply_text(
                t("menu.customer_title", language=lang, name=user.first_name or user.full_name or ""),
                reply_markup=build_customer_main_menu(lang),
            )


def _label_map() -> dict[str, CustomerMenuItem]:
    """Build exact localized button label → stable destination mapping."""
    result: dict[str, CustomerMenuItem] = {}
    key_map = {
        CustomerMenuItem.BUY_VPN: "menu.buy_vpn",
        CustomerMenuItem.FREE_TRIAL: "menu.free_trial",
        CustomerMenuItem.MY_KEYS: "menu.my_keys",
        CustomerMenuItem.WALLET: "menu.wallet",
        CustomerMenuItem.PROFILE: "menu.profile",
        CustomerMenuItem.SUPPORT: "menu.support",
        CustomerMenuItem.MISSIONS: "menu.missions",
    }
    for language in ("en", "my"):
        for item, key in key_map.items():
            result[t(key, language=language)] = item
    return result


_LABEL_TO_ITEM = _label_map()
_LABEL_PATTERN = r"^(?:" + "|".join(
    re.escape(label) for label in sorted(_LABEL_TO_ITEM, key=len, reverse=True)
) + r")$"


@log_handler
async def customer_menu_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Route a known customer main-menu button to its Phase 1.2 page."""
    user = _get_user(context)
    message = update.effective_message
    service = _get_navigation_service(context)
    if not _is_customer_surface(user) or message is None or not message.text:
        return

    item = _LABEL_TO_ITEM.get(message.text.strip())
    if item is None:
        return
    if item in {CustomerMenuItem.BUY_VPN, CustomerMenuItem.MY_KEYS, CustomerMenuItem.WALLET, CustomerMenuItem.PROFILE, CustomerMenuItem.SUPPORT}:
        # Dedicated feature handlers own these destinations before the generic navigation group.
        return
    if item == CustomerMenuItem.REFER_FRIENDS:
        from app.handlers.customer_referral import show_referral_menu
        await show_referral_menu(update, context)
        return
    if item == CustomerMenuItem.MISSIONS:
        from app.handlers.customer_missions import show_missions
        await show_missions(update, context)
        return

    lang = _language(user)
    if service is None:
        logger.error("CustomerNavigationService unavailable")
        await message.reply_text(t("common.error", language=lang))
        return

    try:
        destination = await service.open_destination(user.telegram_id, item)
    except ValueError:
        await message.reply_text(t("nav.invalid", language=lang))
        return

    await message.reply_text(
        f"{t(destination.title_key, language=lang)}\n\n"
        f"{t(destination.body_key, language=lang)}",
        reply_markup=build_customer_page_navigation(lang),
    )


@log_handler
async def unknown_customer_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Friendly fallback for text that is neither a command nor menu button."""
    user = _get_user(context)
    message = update.effective_message
    if not _is_customer_surface(user) or message is None:
        return

    lang = _language(user)
    await message.reply_text(
        t("nav.unknown", language=lang),
        reply_markup=build_customer_main_menu(lang),
    )


def register(application: Application) -> None:
    """Register Phase 1.2 customer navigation handlers."""
    application.add_handler(CommandHandler("menu", menu_command), group=10)
    application.add_handler(CommandHandler("home", menu_command), group=10)
    application.add_handler(
        CallbackQueryHandler(navigation_callback, pattern=r"^nav:(home|back)$"),
        group=10,
    )
    from app.handlers.customer_referral import register as register_referral
    register_referral(application)
    from app.handlers.customer_missions import register as register_missions
    register_missions(application)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(_LABEL_PATTERN),
            customer_menu_message,
        ),
        group=10,
    )
    # Keep the fallback late so future feature handlers can run before it.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_customer_message),
        group=90,
    )
    logger.debug("Phase 1.2 customer navigation handlers registered")
