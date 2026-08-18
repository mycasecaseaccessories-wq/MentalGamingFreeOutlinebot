"""Customer-facing Phase 6.3 Missions UI."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import customer_required, log_handler
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.callback_security_service import CallbackSecurityService
from app.services.mission_progress_service import MissionProgressService
from locales.translator import t

logger = logging.getLogger(__name__)


def _user(context):
    return (context.user_data or {}).get(PLATFORM_USER_KEY)


def _lang(user):
    value = getattr(getattr(user, "language", None), "value", getattr(user, "language", "en"))
    return value if value in {"en", "my"} else "en"


def _service(context):
    registry = context.bot_data.get("registry")
    return registry.get_or_none(MissionProgressService) if registry else None


def _callback_service(context):
    registry = context.bot_data.get("registry")
    return registry.get_or_none(CallbackSecurityService) if registry else None


def _status(value: str, language: str) -> str:
    key = f"missions.status.{value}"
    translated = t(key, language=language)
    return value.replace("_", " ").title() if translated == key else translated


@log_handler
@customer_required
async def show_missions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _user(context)
    message = update.effective_message
    service = _service(context)
    if user is None or message is None or service is None:
        return
    language = _lang(user)
    try:
        missions = await service.get_user_missions(user.id)
    except Exception:
        logger.exception("Mission list failed")
        await message.reply_text(t("missions.error", language=language))
        return
    if not missions:
        await message.reply_text(t("missions.none", language=language))
        return
    buttons = []
    for mission in missions:
        progress = mission.get("progress")
        label = mission["name"]
        if progress:
            label = f"{label} · {progress['progress_value']}/{progress['target_value']}"
        buttons.append([InlineKeyboardButton(label[:64], callback_data=f"mission:detail:{mission['public_mission_id']}")])
    await message.reply_text(t("missions.title", language=language) + "\n\n" + t("missions.body", language=language), reply_markup=InlineKeyboardMarkup(buttons))


async def mission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = _user(context)
    service = _service(context)
    if query is None or user is None or service is None:
        return
    await query.answer()
    callback_security = _callback_service(context)
    callback_data = query.data or ""
    if callback_data.startswith("cb2:"):
        if callback_security is None:
            return
        action_type = await callback_security.action_type_for(callback_data)
        if action_type != "mission.claim":
            return
        rate = await callback_security.check_rate_limit(actor_user_id=user.id, action_type="mission.claim", chat_id=update.effective_chat.id if update.effective_chat else None, limit=5, window_seconds=60)
        if not rate.is_success or not rate.unwrap():
            await query.edit_message_text(t("missions.reward_pending", language=_lang(user)))
            return
        consumed = await callback_security.consume(
            callback_data=callback_data,
            action_type="mission.claim",
            actor_user_id=user.id,
            actor_telegram_id=user.telegram_id,
            chat_id=update.effective_chat.id if update.effective_chat else None,
            chat_type=update.effective_chat.type if update.effective_chat else None,
            expected_resource_type="mission_progress",
        )
        if not consumed.is_success:
            await query.edit_message_text(t("missions.not_claimable", language=_lang(user)))
            return
        progress_id = consumed.unwrap().resource_public_id
        if not progress_id:
            await query.edit_message_text(t("missions.not_claimable", language=_lang(user)))
            return
        result = await service.claim_reward(user_id=user.id, public_progress_id=progress_id)
        text = t("missions.reward_granted", language=_lang(user)) if result.get("status") in {"already_granted", "granted"} else t("missions.not_claimable", language=_lang(user))
        await query.edit_message_text(text)
        return
    parts = callback_data.split(":", 2)
    if len(parts) != 3:
        return
    action, public_id = parts[1], parts[2]
    language = _lang(user)
    if action == "detail":
        missions = await service.get_user_missions(user.id, include_unavailable=True)
        mission = next((item for item in missions if item["public_mission_id"] == public_id), None)
        if mission is None or not mission.get("available", False):
            await query.edit_message_text(t("missions.unavailable", language=language))
            return
        progress = mission.get("progress")
        if progress is None:
            body = t("missions.progress", language=language, name=mission["name"], progress=0, target=mission["progress_target"], status=_status("not_started", language))
            keyboard = None
        else:
            body = t("missions.progress", language=language, name=mission["name"], progress=progress["progress_value"], target=progress["target_value"], status=_status(progress["status"], language))
            keyboard = None
            if progress["status"] in {"reward_pending", "completed"} and mission["delivery_mode"] == "manual_claim":
                claim_data = None
                if callback_security is not None:
                    issued = await callback_security.issue(
                        action_type="mission.claim",
                        actor_user_id=user.id,
                        actor_telegram_id=user.telegram_id,
                        chat_id=update.effective_chat.id if update.effective_chat else None,
                        chat_type=update.effective_chat.type if update.effective_chat else None,
                        resource_type="mission_progress",
                        resource_public_id=progress["public_progress_id"],
                        safe_metadata={"surface": "mission_claim"},
                    )
                    if issued.is_success:
                        claim_data = issued.unwrap().data
                if claim_data:
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t("missions.claim", language=language), callback_data=claim_data)]])
        await query.edit_message_text(f"{body}\n\n{mission['description']}", reply_markup=keyboard)
        return
    if action == "claim":
        if not query.data.startswith("cb2:") or callback_security is None:
            await query.edit_message_text(t("missions.not_claimable", language=language))
            return
        action_type = await callback_security.action_type_for(query.data)
        if action_type != "mission.claim":
            return
        rate = await callback_security.check_rate_limit(actor_user_id=user.id, action_type="mission.claim", chat_id=update.effective_chat.id if update.effective_chat else None, limit=5, window_seconds=60)
        if not rate.is_success or not rate.unwrap():
            await query.edit_message_text(t("missions.reward_pending", language=language))
            return
        consumed = await callback_security.consume(
            callback_data=query.data,
            action_type="mission.claim",
            actor_user_id=user.id,
            actor_telegram_id=user.telegram_id,
            chat_id=update.effective_chat.id if update.effective_chat else None,
            chat_type=update.effective_chat.type if update.effective_chat else None,
            expected_resource_type="mission_progress",
            expected_resource_public_id=public_id,
        )
        if not consumed.is_success:
            await query.edit_message_text(t("missions.not_claimable", language=language))
            return
        public_id = consumed.unwrap().resource_public_id or public_id
        result = await service.claim_reward(user_id=user.id, public_progress_id=public_id)
        if result.get("status") in {"already_granted", "granted"}:
            text = t("missions.reward_granted", language=language)
        elif result.get("status") == "not_claimable":
            text = t("missions.not_claimable", language=language)
        else:
            text = t("missions.reward_pending", language=language)
        await query.edit_message_text(text)


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(mission_callback, pattern=r"^mission:(detail|claim):"), group=11)
    application.add_handler(CallbackQueryHandler(mission_callback, pattern=r"^cb2:"), group=11)
