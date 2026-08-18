"""Phase 7.3 Admin durable-jobs operations view."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.handlers.base import permission_required
from app.services.background_job_service import BackgroundJobService
from locales.translator import t


def _language(context: ContextTypes.DEFAULT_TYPE) -> str:
    value = (context.user_data or {}).get("language", "en")
    return value if value in {"en", "my"} else "en"


def _service(context: ContextTypes.DEFAULT_TYPE) -> BackgroundJobService | None:
    registry = context.bot_data.get("registry")
    return registry.get_or_none(BackgroundJobService) if registry else None


def _keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.jobs.refresh", language=language), callback_data="admin:jobs:refresh")],
        [InlineKeyboardButton(t("admin.jobs.recover", language=language), callback_data="admin:jobs:recover")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
    ])


def _summary(rows: list[dict], language: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [t("admin.jobs.title", language=language), "", t("admin.jobs.total", language=language, count=len(rows))]
    for status in ("ready", "leased", "running", "retry_wait", "succeeded", "failed", "dead_letter"):
        if counts.get(status, 0):
            lines.append(t("admin.jobs.status", language=language, status=status, count=counts[status]))
    lines.append("")
    for row in rows[:12]:
        lines.append(f"• {row['job_type']} · {row['status']} · {row['attempt_count']}/{row['max_attempts']} · {row['public_id']}")
    return "\n".join(lines)


@permission_required("manage_jobs")
async def admin_jobs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    service = _service(context)
    if query is None or message is None or service is None:
        return
    await query.answer()
    language = _language(context)
    parts = (query.data or "").split(":")
    if len(parts) >= 3 and parts[2] == "recover":
        result = await service.recover_stale(limit=100)
        text = t("admin.jobs.recovered", language=language, recovered=result["recovered"], dead_lettered=result["dead_lettered"])
    else:
        text = _summary(await service.list_jobs(limit=100), language)
    await query.edit_message_text(text, reply_markup=_keyboard(language))


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(admin_jobs_callback, pattern=r"^admin:jobs:(?:menu|refresh|recover)$"), group=7)
