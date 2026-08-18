"""Phase 8.1 Admin Security Center."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.services.admin_authorization_service import AdminAuthorizationService
from locales.translator import t


def _service(context: ContextTypes.DEFAULT_TYPE) -> AdminAuthorizationService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(AdminAuthorizationService) if registry else None


def _language(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = (context.user_data or {}).get("platform_user")
    value = getattr(getattr(user, "language", None), "value", None) or getattr(
        user, "language", None
    )
    return value if value in {"en", "my"} else "en"


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Administrators", callback_data="admin:security:admins")],
            [InlineKeyboardButton("📜 Admin Audit", callback_data="admin:security:audit")],
            [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
        ]
    )


@permission_required("view_audit")
async def admin_security_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    service = _service(context)
    if query is None or message is None or service is None:
        return
    await query.answer()
    language = _language(context)
    action = (query.data or "").split(":")[-1]
    if action == "admins":
        rows = await service.list_admins(limit=20)
        lines = ["🔐 Admin Security — Administrators", ""]
        for row in rows:
            permissions = ", ".join(sorted(row.permissions)) or "—"
            lines.append(f"{row.public_id} · {row.role} · {row.status} · {permissions}")
        if not rows:
            lines.append("No administrators found.")
        await query.edit_message_text("\n".join(lines), reply_markup=_keyboard(language))
        return
    if action == "audit":
        rows = await service.list_audit(limit=20)
        lines = ["📜 Admin Audit", ""]
        for row in rows:
            lines.append(f"{row['action']} · {row['entity_type']}:{row['entity_id'] or '—'}")
        if not rows:
            lines.append("No security audit records found.")
        await query.edit_message_text("\n".join(lines), reply_markup=_keyboard(language))
        return
    await query.edit_message_text(
        "🔐 Admin Security\n\nAuthoritative status, permissions, sessions, and audit controls.",
        reply_markup=_keyboard(language),
    )


def register(application: Application) -> None:
    application.add_handler(
        CallbackQueryHandler(
            admin_security_callback,
            pattern=r"^admin:security:(?:menu|admins|audit)$",
        ),
        group=7,
    )
