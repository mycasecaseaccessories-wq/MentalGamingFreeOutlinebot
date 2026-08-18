"""Phase 7.4 Admin Backup & Disaster Recovery controls."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.services.backup_service import BackupService
from locales.translator import t


def _actor(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _language(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = (context.user_data or {}).get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _service(context: ContextTypes.DEFAULT_TYPE) -> BackupService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(BackupService) if registry else None


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.backup.create", language=language), callback_data="admin:backup:create")],
        [InlineKeyboardButton(t("admin.backup.verify_latest", language=language), callback_data="admin:backup:verify_latest")],
        [InlineKeyboardButton(t("admin.backup.restore_test", language=language), callback_data="admin:backup:restore_test")],
        [InlineKeyboardButton(t("admin.backup.retention", language=language), callback_data="admin:backup:retention")],
        [InlineKeyboardButton(t("admin.backup.refresh", language=language), callback_data="admin:backup:refresh")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
    ])


def _overview(rows: list[dict], language: str) -> str:
    verified = sum(1 for row in rows if row["status"] == "verified")
    restore_tested = sum(1 for row in rows if row["restore_test_status"] == "passed")
    failed = sum(1 for row in rows if row["status"] in {"failed", "corrupted"})
    lines = [
        t("admin.backup.title", language=language),
        "",
        t("admin.backup.summary", language=language, total=len(rows), verified=verified, restore_tested=restore_tested, failed=failed),
        t("admin.backup.rpo_rto", language=language),
        "",
    ]
    for row in rows[:10]:
        restore = row["restore_test_status"]
        lines.append(f"• {row['public_id']} · {row['status']} · verify={row['verification_status']} · restore={restore}")
    if not rows:
        lines.append(t("admin.backup.empty", language=language))
    return "\n".join(lines)


@permission_required("manage_backups")
async def admin_backup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    actor_id = _actor(update)
    service = _service(context)
    if query is None or actor_id is None or service is None:
        return
    await query.answer()
    language = _language(context)
    action = (query.data or "").split(":")[-1]
    if action == "create":
        result = await service.create_backup(backup_type="manual", retention_class="daily", created_by=actor_id)
        text = t("admin.backup.action_result", language=language, action=t("admin.backup.create", language=language), status=result.get("status"), error=result.get("safe_error_code") or "—")
    elif action == "verify_latest":
        rows = await service.list_backups(limit=1)
        result = await service.verify_backup(rows[0]["public_id"]) if rows else {"status": "failed", "safe_error_code": "no_backup"}
        text = t("admin.backup.action_result", language=language, action=t("admin.backup.verify_latest", language=language), status=result.get("status"), error=result.get("safe_error_code") or "—")
    elif action == "restore_test":
        result = await service.run_latest_restore_test()
        text = t("admin.backup.restore_result", language=language, status=result.get("status"), error=result.get("safe_error_code") or "—")
    elif action == "retention":
        result = await service.apply_retention()
        text = t("admin.backup.retention_result", language=language, deleted=result.get("deleted", 0))
    else:
        text = _overview(await service.list_backups(limit=100), language)
    await query.edit_message_text(text, reply_markup=_keyboard(language))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_backup_callback, pattern=r"^admin:backup:(?:menu|create|verify_latest|restore_test|retention|refresh)$"), group=7)
