"""Admin Maintenance Control and Operational Incident Center."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.maintenance_service import MaintenanceScope, MaintenanceService, MaintenanceState
from locales.translator import t


def _language(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = (context.user_data or {}).get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _service(context: ContextTypes.DEFAULT_TYPE) -> MaintenanceService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(MaintenanceService) if registry else None


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.maintenance.start_global", language=language), callback_data="admin:maintenance:start_global")],
        [InlineKeyboardButton(t("admin.maintenance.end", language=language), callback_data="admin:maintenance:end")],
        [InlineKeyboardButton(t("admin.maintenance.incidents", language=language), callback_data="admin:maintenance:incidents")],
        [InlineKeyboardButton(t("admin.maintenance.refresh", language=language), callback_data="admin:maintenance:refresh")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
    ])


def _state_text(windows: list[dict], language: str) -> str:
    if not windows:
        return t("admin.maintenance.no_active", language=language)
    return "\n".join(t("admin.maintenance.window", language=language, scope=row["scope"], state=row["state"].upper(), status=row["status"]) for row in windows)


@permission_required("manage_maintenance")
async def admin_maintenance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    actor_id = update.effective_user.id if update.effective_user else None
    service = _service(context)
    if query is None or message is None or actor_id is None or service is None:
        return
    await query.answer()
    language = _language(context)
    action = (query.data or "").split(":")[-1]
    if action in {"menu", "refresh"}:
        windows = await service.list_windows(active_only=True)
        incidents = await service.list_incidents(active_only=True, limit=20)
        text = f"{t('admin.maintenance.title', language=language)}\n\n{t('admin.maintenance.active', language=language, count=len(windows))}\n{_state_text(windows, language)}"
        if incidents:
            text += f"\n\n{t('admin.maintenance.incident_title', language=language)}\n{len(incidents)}"
        await query.edit_message_text(text, reply_markup=_keyboard(language))
        return
    if action == "start_global":
        await service.schedule_maintenance(scope=MaintenanceScope.GLOBAL, state=MaintenanceState.EMERGENCY, created_by=actor_id, customer_message_key="maintenance.message")
        await query.edit_message_text(t("admin.maintenance.started", language=language), reply_markup=_keyboard(language))
        return
    if action == "end":
        windows = await service.list_windows(active_only=True)
        if not windows:
            await query.edit_message_text(t("admin.maintenance.no_active", language=language), reply_markup=_keyboard(language))
            return
        window = windows[0]
        check = await service.recovery_check(window["scope"])
        result = await service.end_maintenance(window["public_id"], ended_by=actor_id, recovery_ok=check["healthy"])
        text = t("admin.maintenance.ended", language=language) if result.get("ended") else t("admin.maintenance.blocked", language=language)
        await query.edit_message_text(text, reply_markup=_keyboard(language))
        return
    if action == "incidents":
        incidents = await service.list_incidents(active_only=True, limit=10)
        if not incidents:
            text = t("admin.maintenance.no_incidents", language=language)
        else:
            text = t("admin.maintenance.incident_title", language=language) + "\n\n" + "\n\n".join(t("admin.maintenance.incident", language=language, severity=item["severity"].upper(), status=item["status"], title=item["title"], impact=item["customer_impact"], summary=item["safe_summary"]) for item in incidents)
        await query.edit_message_text(text, reply_markup=_keyboard(language))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_maintenance_callback, pattern=r"^admin:maintenance:(?:menu|refresh|start_global|end|incidents)$"), group=7)
