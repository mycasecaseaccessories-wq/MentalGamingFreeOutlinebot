"""Phase 1.5 owner-scoped My Keys UI."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.keyboards.customer_keys import build_key_detail_keyboard, build_key_list_keyboard
from app.middlewares.auth import PLATFORM_USER_KEY


async def show_keys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = context.user_data.get(PLATFORM_USER_KEY)
    message = update.effective_message
    service = context.bot_data.get("customer_key_service")
    if user is None or message is None or service is None:
        return
    items = await service.list_owned(user.telegram_id)
    if not items:
        await message.reply_text("🔑 You do not have any VPN keys yet.\nUse 🛒 Buy VPN to get started.")
        return
    lines = ["🔑 My VPN Keys", ""]
    for item in items:
        lines.append(f"• Key #{item.key_id} — {item.status}")
    await message.reply_text("\n".join(lines),
                             reply_markup=build_key_list_keyboard([item.key_id for item in items]))


async def key_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = context.user_data.get(PLATFORM_USER_KEY)
    service = context.bot_data.get("customer_key_service")
    if user is None or service is None:
        return
    _, action, raw_id = query.data.split(":", 2)
    key_id = int(raw_id)
    detail = await service.get_owned(user.telegram_id, key_id)
    if detail is None:
        await query.edit_message_text("🔒 Key not found.")
        return
    if action == "renew":
        await query.edit_message_text("🔄 Renewal will be available in a later phase.")
    elif action == "connect":
        await query.edit_message_text("🔗 Connection details are available after the VPN engine is enabled.")
    else:
        await query.edit_message_text(
            f"🔑 Key #{detail.key_id}\nStatus: {detail.status}\n"
            f"Used: {detail.used_bytes} bytes",
            reply_markup=build_key_detail_keyboard(key_id),
        )


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(key_callback, pattern=r"^keys:"))