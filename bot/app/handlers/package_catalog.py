"""Phase 1.4 read-only package catalogue UI."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.keyboards.package_catalog import build_package_detail_keyboard, build_package_list_keyboard
from app.middlewares.auth import PLATFORM_USER_KEY


async def show_packages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service = context.bot_data.get("package_catalog_service")
    message = update.effective_message
    if service is None or message is None:
        return
    page = await service.list_visible()
    if not page.items:
        await message.reply_text("📦 No VPN packages are available yet.")
        return
    lines = ["📦 Available VPN packages", ""]
    for item in page.items:
        lines.append(f"• {item.name} — {item.price} {item.currency} / {item.duration_days} days")
    await message.reply_text("\n".join(lines),
                             reply_markup=build_package_list_keyboard([item.package_id for item in page.items]))


async def package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    service = context.bot_data.get("package_catalog_service")
    if service is None:
        return
    _, action, raw_id = query.data.split(":", 2)
    package_id = int(raw_id)
    item = await service.get_visible(package_id)
    if item is None:
        await query.edit_message_text("This package is no longer available.")
        return
    if action == "select":
        user = context.user_data.get(PLATFORM_USER_KEY)
        selection = await service.select(user.telegram_id, package_id) if user else None
        if selection is None:
            await query.edit_message_text("This package is no longer available.")
            return
        await query.edit_message_text(
            f"✅ Selected: {selection.package_name}\n"
            f"Quoted price: {selection.quoted_price} {selection.currency}\n\n"
            "Checkout will be available in Phase 2."
        )
        return
    await query.edit_message_text(
        f"📦 {item.name}\n\n{item.description or 'VPN access package'}\n"
        f"Price: {item.price} {item.currency}\nDuration: {item.duration_days} days",
        reply_markup=build_package_detail_keyboard(package_id),
    )


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(package_callback, pattern=r"^catalog:"))