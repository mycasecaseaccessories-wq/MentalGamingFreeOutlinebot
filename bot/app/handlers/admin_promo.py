from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import admin_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.promo_service import PromoService
from app.services.promo_redemption_service import PromoRedemptionService
from database.models.promo import PromoCodeORM
from locales.translator import t


def _registry(context):
    return context.bot_data.get("registry")


def _lang(context):
    user = (context.user_data or {}).get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _promo_service(context):
    registry = _registry(context)
    return registry.get_or_none(PromoService) if registry else None


def _redemption_service(context):
    registry = _registry(context)
    return registry.get_or_none(PromoRedemptionService) if registry else None


def _menu(language, rows):
    buttons = [[InlineKeyboardButton(f"{row['code']} · {row['status']}", callback_data=f"admin:promo:detail:{row['public_promo_id']}")] for row in rows]
    buttons.append([InlineKeyboardButton(t("common.back", language=language), callback_data="admin:home")])
    return InlineKeyboardMarkup(buttons)


@admin_required
async def admin_promo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    parts = (query.data or "").split(":")
    language = _lang(context)
    service = _promo_service(context)
    if service is None:
        await query.edit_message_text(t("common.error", language=language))
        return
    if parts[:3] in (["admin", "promo", "menu"], ["admin", "promo", "list"]):
        rows = await service.list_promos()
        await query.edit_message_text(t("admin.promo.menu", language=language) + "\n\n" + ("\n".join(f"{r['code']} — {r['status']} — {r['completed_count']}/{r['max_redemptions'] or '∞'}" for r in rows) or t("promo.history_empty", language=language)), reply_markup=_menu(language, rows))
        return
    if len(parts) == 4 and parts[:3] == ["admin", "promo", "detail"]:
        row = await service.get_by_public_id(parts[3])
        if row is None:
            await query.edit_message_text(t("admin.promo.not_found", language=language))
            return
        data = service.to_dict(row)
        buttons = []
        if data["status"] == PromoCodeORM.STATUS_ACTIVE:
            buttons.append(InlineKeyboardButton(t("admin.promo.pause", language=language), callback_data=f"admin:promo:status:{data['public_promo_id']}:paused"))
        elif data["status"] == PromoCodeORM.STATUS_PAUSED:
            buttons.append(InlineKeyboardButton(t("admin.promo.resume", language=language), callback_data=f"admin:promo:status:{data['public_promo_id']}:active"))
        if data["status"] != PromoCodeORM.STATUS_ARCHIVED:
            buttons.append(InlineKeyboardButton(t("admin.promo.archive", language=language), callback_data=f"admin:promo:status:{data['public_promo_id']}:archived"))
        text = f"{data['code']}\n\nStatus: {data['status']}\nType: {data['promo_type']}\nReward: {data['reward_type']} {data['reward_value']}\nUsage: {data['completed_count']}/{data['max_redemptions'] or '∞'}\nPer user: {data['max_redemptions_per_user']}\nRevision: {data['policy_revision']}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([buttons, [InlineKeyboardButton(t("common.back", language=language), callback_data="admin:promo:list")]]))
        return
    if len(parts) == 5 and parts[:3] == ["admin", "promo", "status"]:
        status = parts[4]
        if status not in {PromoCodeORM.STATUS_ACTIVE, PromoCodeORM.STATUS_PAUSED, PromoCodeORM.STATUS_DISABLED, PromoCodeORM.STATUS_ARCHIVED}:
            await query.answer(t("common.error", language=language), show_alert=True)
            return
        await service.set_status(parts[3], status)
        rows = await service.list_promos()
        await query.edit_message_text(t("admin.promo.menu", language=language), reply_markup=_menu(language, rows))
        return


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_promo_callback, pattern=r"^admin:promo:(?:menu|list|detail:[A-Za-z0-9-]+|status:[A-Za-z0-9-]+:(?:active|paused|disabled|archived))$"), group=7)
