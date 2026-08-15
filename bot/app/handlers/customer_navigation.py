"""Phase 1.2 customer navigation handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.keyboards.customer_account import build_customer_menu
from app.middlewares.auth import PLATFORM_USER_KEY
from app.models.navigation import CustomerPage
from app.services.customer_navigation_service import CustomerNavigationService


async def _open(update: Update, context: ContextTypes.DEFAULT_TYPE, page: CustomerPage) -> None:
    user = context.user_data.get(PLATFORM_USER_KEY)
    message = update.effective_message
    if user is None or message is None:
        return
    service = context.bot_data.get("customer_navigation_service")
    if service is not None:
        await service.open(user.telegram_id, page)
    lang = user.language.value
    labels = {
        CustomerPage.PACKAGES: ("🛒 Buy VPN", "Package catalogue will open here."),
        CustomerPage.FREE_TRIAL: ("🎁 Free Trial", "Free-trial eligibility will be available soon."),
        CustomerPage.MY_KEYS: ("🔑 My Keys", "Your VPN keys are shown here."),
        CustomerPage.WALLET: ("💰 Wallet", "Wallet and payment features are coming soon."),
        CustomerPage.PROFILE: ("👤 Profile", f"Name: {user.full_name}\nTelegram ID: {user.telegram_id}"),
        CustomerPage.SUPPORT: ("🎫 Support", "Please contact support for assistance."),
    }
    title, body = labels.get(page, ("🏠 Home", "Choose an option from the menu."))
    await message.reply_text(f"{title}\n\n{body}", reply_markup=build_customer_menu(lang))


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _open(update, context, CustomerPage.HOME)


async def packages_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.handlers.package_catalog import show_packages
    await show_packages(update, context)


async def keys_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.handlers.customer_keys import show_keys
    await show_keys(update, context)


def register(application: Application) -> None:
    application.add_handler(MessageHandler(filters.Regex(r"^(🛒 Buy VPN|🛒 VPN ဝယ်ရန်)$"), packages_text))
    application.add_handler(MessageHandler(filters.Regex(r"^(🔑 My Keys)$"), keys_text))
    application.add_handler(MessageHandler(filters.Regex(r"^(🎁 Free Trial|🎁 အခမဲ့စမ်းသုံးရန်)$"),
                                            lambda u, c: _open(u, c, CustomerPage.FREE_TRIAL)))
    application.add_handler(MessageHandler(filters.Regex(r"^(💰 Wallet)$"),
                                            lambda u, c: _open(u, c, CustomerPage.WALLET)))
    application.add_handler(MessageHandler(filters.Regex(r"^(👤 Profile|👤 ကိုယ်ရေးအချက်အလက်)$"),
                                            lambda u, c: _open(u, c, CustomerPage.PROFILE)))
    application.add_handler(MessageHandler(filters.Regex(r"^(🎫 Support|🎫 အကူအညီ)$"),
                                            lambda u, c: _open(u, c, CustomerPage.SUPPORT)))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("home", menu_command))