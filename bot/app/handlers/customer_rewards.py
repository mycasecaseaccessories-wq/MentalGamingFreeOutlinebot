"""Phase 6.6 customer Rewards Center and Entitlements Center."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import log_handler
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.growth_reward_service import GrowthRewardService
from locales.translator import t


def _user(context: ContextTypes.DEFAULT_TYPE):
    return (context.user_data or {}).get(PLATFORM_USER_KEY)


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = _user(context)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _service(context: ContextTypes.DEFAULT_TYPE) -> GrowthRewardService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(GrowthRewardService) if registry else None


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("rewards.history", language=language), callback_data="growth:rewards:history")],
        [InlineKeyboardButton(t("rewards.entitlements", language=language), callback_data="growth:rewards:entitlements")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def _status(value: str, language: str) -> str:
    keys = {
        "granted": "status.granted",
        "pending": "status.pending",
        "review_required": "status.review_required",
        "failed": "status.failed",
        "cancelled": "status.cancelled",
        "limit_reached": "status.limit_reached",
    }
    key = keys.get(value)
    return t(key, language=language) if key else value.replace("_", " ").title()


@log_handler
async def show_rewards_center(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _user(context)
    message = update.effective_message
    service = _service(context)
    if user is None or message is None or service is None:
        return
    language = _lang(context)
    result = await service.customer_center(user.id)
    if not result.is_success:
        await message.reply_text(t("rewards.error", language=language))
        return
    data = result.unwrap()
    counts = data["counts"]
    text = t("rewards.title", language=language) + "\n\n" + t(
        "rewards.summary", language=language,
        rewards=counts["rewards"], granted=counts["granted"],
        pending=counts["pending"], entitlements=counts["available_entitlements"],
    )
    await message.reply_text(text, reply_markup=_keyboard(language))


async def rewards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = _user(context)
    service = _service(context)
    if query is None or user is None or service is None:
        return
    await query.answer()
    language = _lang(context)
    data = (await service.customer_center(user.id)).unwrap()
    if query.data == "growth:rewards:history":
        rows = data["rewards"]
        if not rows:
            text = t("rewards.empty", language=language)
        else:
            text = t("rewards.history", language=language)
            for row in rows:
                text += "\n\n" + t(
                    "rewards.history_item", language=language,
                    source=row["source_type"].title(),
                    reward=row["reward_label"],
                    status=_status(row["status"], language),
                )
        await query.edit_message_text(text, reply_markup=_keyboard(language))
        return
    if query.data == "growth:rewards:entitlements":
        rows = data["entitlements"]
        if not rows:
            text = t("rewards.empty", language=language)
        else:
            text = t("rewards.entitlements", language=language)
            for row in rows:
                value = row["data_label"] or row["duration_label"] or f"{row['remaining_uses']} use(s)"
                text += "\n\n" + t(
                    "rewards.entitlement_item", language=language,
                    source=row["source"], value=value, status=row["status"].title(),
                )
        await query.edit_message_text(text, reply_markup=_keyboard(language))
        return


def register(application: Application) -> None:
    application.add_handler(
        CallbackQueryHandler(rewards_callback, pattern=r"^growth:rewards:(history|entitlements)$"),
        group=12,
    )
