from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import log_handler
from app.keyboards.main_menu import build_customer_main_menu, build_customer_page_navigation
from app.middlewares.auth import PLATFORM_USER_KEY
from app.models.enums import UserRole
from app.services.promo_redemption_service import PromoRedemptionService
from locales.translator import t

_ROLES = {UserRole.CUSTOMER, UserRole.VIP, UserRole.RESELLER, UserRole.AFFILIATE}


def _user(context):
    return (context.user_data or {}).get(PLATFORM_USER_KEY)


def _lang(user):
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _service(context) -> PromoRedemptionService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(PromoRedemptionService) if registry else None


def _reward_label(result: dict, lang: str) -> str:
    reward = result.get("reward_type") or result.get("promo_reward_type") or "reward"
    key = {"extra_free_trial": "promo.reward_extra_trial", "extra_trial": "promo.reward_extra_trial", "wallet_credit": "promo.reward_wallet", "bonus_data": "promo.reward_data", "bonus_duration": "promo.reward_duration", "percent_discount": "promo.reward_discount", "fixed_discount": "promo.reward_discount"}.get(reward, "promo.reward_discount")
    return t(key, language=lang)


async def show_promo_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _user(context)
    message = update.effective_message
    if user is None or user.role not in _ROLES or message is None:
        return
    lang = _lang(user)
    context.user_data["promo_entry_mode"] = True
    await message.reply_text(t("promo.prompt", language=lang), reply_markup=build_customer_page_navigation(lang))


@log_handler
async def promo_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _user(context)
    message = update.effective_message
    if user is None or user.role not in _ROLES or message is None or not message.text:
        return
    if not (context.user_data or {}).get("promo_entry_mode"):
        return
    context.user_data["promo_entry_mode"] = False
    service = _service(context)
    lang = _lang(user)
    if service is None:
        await message.reply_text(t("common.error", language=lang))
        return
    try:
        result = await service.redeem(user_id=user.id, code=message.text.strip())
    except ValueError:
        result = {"status": "failed", "error_code": "invalid_promo_code"}
    if result.get("status") == "completed":
        await message.reply_text(t("promo.applied", language=lang, code=message.text.strip().upper(), reward=_reward_label(result, lang)), reply_markup=build_customer_main_menu(lang))
        return
    key = {"invalid_promo_code": "promo.invalid", "promo_not_active": "promo.not_active", "promo_expired": "promo.expired", "already_used": "promo.already_used", "usage_limit_reached": "promo.limit_reached", "not_eligible": "promo.not_eligible", "minimum_purchase_not_met": "promo.minimum_purchase"}.get(result.get("error_code"), "promo.try_again")
    await message.reply_text(t(key, language=lang), reply_markup=build_customer_main_menu(lang))


async def promo_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = _user(context)
    if query is None or user is None or user.role not in _ROLES:
        return
    await query.answer()
    service = _service(context)
    lang = _lang(user)
    if service is None:
        await query.message.reply_text(t("common.error", language=lang))
        return
    rows = await service.history(user.id)
    if not rows:
        await query.message.reply_text(t("promo.history_empty", language=lang))
        return
    lines = [t("promo.history_title", language=lang)]
    for row in rows:
        lines.append(t("promo.history_item", language=lang, code=row.get("public_redemption_id"), reward=row.get("reward_reference") or "Promo reward", status=row.get("status")))
    await query.message.reply_text("\n".join(lines))


def register(application: Application) -> None:
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, promo_text), group=20)
    application.add_handler(CallbackQueryHandler(promo_history, pattern=r"^promo:history$"), group=20)
