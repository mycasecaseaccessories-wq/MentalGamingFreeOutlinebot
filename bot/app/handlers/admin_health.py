"""Phase 7.1 Admin System Health dashboard."""
from __future__ import annotations

from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.health_service import HealthCheckResult, HealthService, HealthSnapshot, OperationalHealthStatus
from locales.translator import t


def _actor(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _language(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = (context.user_data or {}).get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _service(context: ContextTypes.DEFAULT_TYPE) -> HealthService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(HealthService) if registry else None


def _icon(status: OperationalHealthStatus) -> str:
    return {
        OperationalHealthStatus.HEALTHY: "🟢",
        OperationalHealthStatus.DEGRADED: "🟡",
        OperationalHealthStatus.UNHEALTHY: "🔴",
        OperationalHealthStatus.UNKNOWN: "⚪",
        OperationalHealthStatus.DISABLED: "⚫",
        OperationalHealthStatus.STALE: "🟠",
    }.get(status, "⚪")


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.health.servers", language=language), callback_data="admin:health:component:vpn_servers")],
        [InlineKeyboardButton(t("admin.health.workers", language=language), callback_data="admin:health:component:workers")],
        [InlineKeyboardButton(t("admin.health.providers", language=language), callback_data="admin:health:component:providers")],
        [InlineKeyboardButton(t("admin.health.failures", language=language), callback_data="admin:health:component:failures")],
        [InlineKeyboardButton(t("admin.health.capacity", language=language), callback_data="admin:health:component:capacity")],
        [InlineKeyboardButton(t("admin.health.refresh", language=language), callback_data="admin:health:refresh")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
    ])


def _format_time(value: datetime, language: str) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _component(snapshot: HealthSnapshot, name: str) -> HealthCheckResult | None:
    return next((item for item in snapshot.components if item.component == name), None)


def _overview(snapshot: HealthSnapshot, language: str) -> str:
    lines = [
        t("admin.health.title", language=language),
        "",
        t("admin.health.overall", language=language, status=f"{_icon(snapshot.overall)} {snapshot.overall.value.upper()}"),
    ]
    for item in snapshot.components:
        label = t(f"admin.health.component.{item.component}", language=language)
        details = item.safe_details
        suffix = ""
        if item.component == "vpn_servers":
            suffix = f" ({details.get('healthy', 0)}/{details.get('total', 0)})"
        elif item.latency_ms is not None:
            suffix = f" · {item.latency_ms}ms"
        lines.append(f"{_icon(item.status)} {label}: {item.status.value.upper()}{suffix}")
    lines.extend([
        "",
        t("admin.health.failed_jobs", language=language, count=snapshot.failed_jobs),
        t("admin.health.stale_operations", language=language, count=snapshot.stale_operations),
        t("admin.health.last_updated", language=language, value=_format_time(snapshot.checked_at, language)),
    ])
    return "\n".join(lines)


@permission_required("manage_health")
async def admin_health_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    actor_id = _actor(update)
    service = _service(context)
    if query is None or message is None or actor_id is None or service is None:
        return
    await query.answer()
    language = _language(context)
    snapshot = await service.check_system()
    parts = (query.data or "").split(":")
    if parts[:3] in (["admin", "health", "menu"], ["admin", "health", "refresh"]):
        await query.edit_message_text(_overview(snapshot, language), reply_markup=_keyboard(language))
        return
    if len(parts) == 4 and parts[:3] == ["admin", "health", "component"]:
        component = parts[3]
        if component == "capacity":
            capacity = snapshot.capacity
            text = t("admin.health.capacity_detail", language=language, servers=capacity.get("servers", "—"), users=capacity.get("current_users", "—"), max_users=capacity.get("max_users", "—"), keys=capacity.get("existing_keys", "—"), max_keys=capacity.get("max_keys", "—"), user_utilization=capacity.get("user_utilization_percent", "—"), key_utilization=capacity.get("key_utilization_percent", "—"))
        elif component == "failures":
            text = t("admin.health.failures_detail", language=language, failed=snapshot.failed_jobs, stale=snapshot.stale_operations)
        elif component == "providers":
            rows = [item for item in snapshot.components if item.component in {"outline_apis", "payments", "notifications"}]
            provider_details = "\n".join(f"{_icon(item.status)} {item.component}: {item.message_code}" for item in rows)
            text = t("admin.health.providers_detail", language=language, details=provider_details)
        else:
            item = _component(snapshot, component)
            if item is None:
                text = t("admin.health.component_unknown", language=language)
            else:
                text = t("admin.health.component_detail", language=language, component=t(f"admin.health.component.{item.component}", language=language), status=f"{_icon(item.status)} {item.status.value.upper()}", message=item.message_code or "—", latency=item.latency_ms if item.latency_ms is not None else "—", details=str(item.safe_details) if item.safe_details else "—")
        await query.edit_message_text(text, reply_markup=_keyboard(language))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_health_callback, pattern=r"^admin:health:(?:menu|refresh|component:[a-z_]+)$"), group=7)
