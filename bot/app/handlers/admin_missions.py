"""Admin-facing Phase 6.3 mission management UI."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.mission_service import MissionService
from database.models.mission import MissionORM
from locales.translator import t

logger = logging.getLogger(__name__)


def _service(context):
    registry = context.bot_data.get("registry")
    return registry.get_or_none(MissionService) if registry else None


def _lang(context):
    user = (context.user_data or {}).get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _menu(language: str, missions: list[dict]):
    buttons = []
    for mission in missions:
        buttons.append([InlineKeyboardButton(f"{mission['name']} · {mission['status']}", callback_data=f"admin:missions:detail:{mission['public_mission_id']}")])
    buttons.append([InlineKeyboardButton(t("common.back", language=language), callback_data="admin:home")])
    return InlineKeyboardMarkup(buttons)


@permission_required("manage_missions")
async def admin_missions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    service = _service(context)
    if query is None or service is None:
        return
    await query.answer()
    language = _lang(context)
    parts = (query.data or "").split(":")
    if parts[:3] == ["admin", "missions", "menu"] or parts[:3] == ["admin", "missions", "list"]:
        missions = await service.list_missions(include_unavailable=True)
        text = t("admin.missions.menu", language=language) + "\n\n" + ("\n".join(f"{m['public_mission_id']} — {m['name']} — {m['status']}" for m in missions) or t("missions.none", language=language))
        await query.edit_message_text(text, reply_markup=_menu(language, missions))
        return
    if len(parts) == 4 and parts[:3] == ["admin", "missions", "detail"]:
        mission = await service.get(parts[3])
        if mission is None:
            await query.edit_message_text(t("error.not_found", language=language))
            return
        status_buttons = []
        if mission["status"] != MissionORM.STATUS_ACTIVE:
            status_buttons.append(InlineKeyboardButton(t("admin.missions.activate", language=language), callback_data=f"admin:missions:status:{mission['public_mission_id']}:active"))
        if mission["status"] == MissionORM.STATUS_ACTIVE:
            status_buttons.append(InlineKeyboardButton(t("admin.missions.disable", language=language), callback_data=f"admin:missions:status:{mission['public_mission_id']}:disabled"))
        if mission["status"] != MissionORM.STATUS_ARCHIVED:
            status_buttons.append(InlineKeyboardButton(t("admin.missions.archive", language=language), callback_data=f"admin:missions:status:{mission['public_mission_id']}:archived"))
        text = f"{mission['name']}\n{mission['description']}\n\nType: {mission['mission_type']}\nTarget: {mission['progress_target']}\nReward: {mission['reward_type']} {mission['reward_value']}\nDelivery: {mission['delivery_mode']}\nRepeat: {mission['repeat_mode']}\nStatus: {mission['status']}\nRevision: {mission['policy_revision']}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([status_buttons, [InlineKeyboardButton(t("common.back", language=language), callback_data="admin:missions:list")]]))
        return
    if len(parts) == 5 and parts[:3] == ["admin", "missions", "status"]:
        status = parts[4]
        if status not in {MissionORM.STATUS_ACTIVE, MissionORM.STATUS_DISABLED, MissionORM.STATUS_ARCHIVED}:
            await query.answer(t("admin.missions.invalid_config", language=language), show_alert=True)
            return
        result = await service.set_status(parts[3], status)
        if result is None:
            await query.edit_message_text(t("error.not_found", language=language))
            return
        missions = await service.list_missions(include_unavailable=True)
        await query.edit_message_text(t("admin.missions.menu", language=language), reply_markup=_menu(language, missions))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_missions_callback, pattern=r"^admin:missions:(?:menu|list|detail:[A-Za-z0-9-]+|status:[A-Za-z0-9-]+:(?:active|disabled|archived))$"), group=7)
