"""Phase 2.4 admin manual-payment review handlers."""

from __future__ import annotations

import logging
import math
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import admin_required, log_handler, permission_required
from app.middlewares.auth import PLATFORM_USER_KEY
from app.keyboards.admin_payment_review import (
    admin_approval_confirmation_keyboard,
    admin_payment_menu_keyboard,
    admin_pending_queue_keyboard,
    admin_rejection_confirmation_keyboard,
    admin_rejection_reasons_keyboard,
    admin_review_keyboard,
)
from app.models.payment_review import PaymentReviewItem
from app.services.payment_review_service import PaymentReviewService
from database.models.payment_submission import PaymentSubmissionORM
from config import settings
from locales.translator import t

logger = logging.getLogger(__name__)
_ADMIN_REVIEW_KEY = "phase24_admin_review"


def _language(context: ContextTypes.DEFAULT_TYPE) -> str:
    user = context.user_data.get(PLATFORM_USER_KEY)
    value = getattr(getattr(user, "language", None), "value", None) or getattr(user, "language", None)
    return value if value in {"en", "my"} else "en"


def _service(context: ContextTypes.DEFAULT_TYPE) -> PaymentReviewService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(PaymentReviewService)


def _actor_id(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def _money(amount, currency: str) -> str:
    return f"{amount:,.2f} {currency}" if amount != amount.to_integral_value() else f"{int(amount):,} {currency}"


def _submitted(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else "—"


def _item_text(item: PaymentReviewItem, language: str) -> str:
    return t(
        "admin.payments.detail",
        language=language,
        payment=item.public_payment_id,
        order=item.public_order_id,
        customer=item.username or item.customer_name,
        telegram_id=item.telegram_id,
        method=item.payment_method,
        amount=_money(item.amount, item.currency),
        currency=item.currency,
        reference=item.transaction_reference or "—",
        submitted=_submitted(item.submitted_at),
        order_status=item.order_status,
        payment_status=item.order_payment_status,
        proof=t("admin.payments.proof_attached" if item.proof_file_id else "admin.payments.proof_missing", language=language),
    )


async def _show_payment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message:
        await message.reply_text(t("admin.payments.menu", language=_language(context)), reply_markup=admin_payment_menu_keyboard(_language(context)))


@admin_required
@log_handler
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_payment_menu(update, context)


@permission_required("manage_payments")
async def admin_payments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    actor_id = _actor_id(update)
    if query is None or message is None or actor_id is None:
        return
    await query.answer()
    language = _language(context)
    parts = (query.data or "").split(":")
    service = _service(context)
    if service is None:
        await message.reply_text(t("common.error", language=language))
        return
    try:
        if parts == ["admin", "home"]:
            await _show_payment_menu(update, context)
            return
        if parts == ["admin", "payments"]:
            await _show_payment_menu(update, context)
            return
        if len(parts) == 4 and parts[:3] == ["admin", "payments", "pending"]:
            page = max(1, int(parts[3]))
            result = await service.list_pending(page=page)
            if not result.items:
                await message.reply_text(t("admin.payments.pending_empty", language=language), reply_markup=admin_payment_menu_keyboard(language))
                return
            pages = max(1, math.ceil(result.total / result.page_size))
            text = t("admin.payments.queue_header", language=language, page=result.page, pages=pages)
            for item in result.items:
                text += "\n\n" + t(
                    "admin.payments.queue_item",
                    language=language,
                    payment=item.public_payment_id,
                    customer=item.username or item.customer_name,
                    order=item.public_order_id,
                    method=item.payment_method,
                    amount=_money(item.amount, item.currency),
                    submitted=_submitted(item.submitted_at),
                )
            await message.reply_text(text, reply_markup=admin_pending_queue_keyboard(result.page, result.has_previous, result.has_next, language, payment_ids=[item.public_payment_id for item in result.items]))
            return
        if len(parts) == 4 and parts[2] in {"approved", "rejected"}:
            status = PaymentSubmissionORM.STATUS_APPROVED if parts[2] == "approved" else PaymentSubmissionORM.STATUS_REJECTED
            result = await service.list_by_status(status=status, page=max(1, int(parts[3])))
            if not result.items:
                await message.reply_text(t("admin.payments.pending_empty", language=language), reply_markup=admin_payment_menu_keyboard(language))
                return
            pages = max(1, math.ceil(result.total / result.page_size))
            text = t("admin.payments.queue_header", language=language, page=result.page, pages=pages)
            for item in result.items:
                text += "\n\n" + t("admin.payments.queue_item", language=language, payment=item.public_payment_id, customer=item.username or item.customer_name, order=item.public_order_id, method=item.payment_method, amount=_money(item.amount, item.currency), submitted=_submitted(item.submitted_at))
            await message.reply_text(text, reply_markup=admin_pending_queue_keyboard(result.page, result.has_previous, result.has_next, language, parts[2], [item.public_payment_id for item in result.items]))
            return
        if len(parts) == 4 and parts[2] == "view":
            item = await service.get_detail(public_payment_id=parts[3])
            if item is None:
                await message.reply_text(t("error.not_found", language=language))
                return
            await message.reply_text(_item_text(item, language), reply_markup=admin_review_keyboard(item.public_payment_id, language))
            return
        if len(parts) == 4 and parts[2] == "proof":
            item = await service.get_detail(public_payment_id=parts[3])
            if item is None or not item.proof_file_id:
                await message.reply_text(t("admin.payments.proof_missing", language=language))
                return
            if item.proof_file_type == "photo":
                await context.bot.send_photo(chat_id=actor_id, photo=item.proof_file_id)
            else:
                await context.bot.send_document(chat_id=actor_id, document=item.proof_file_id)
            return
        if len(parts) == 4 and parts[2] == "approve":
            item = await service.get_detail(public_payment_id=parts[3])
            if item is None:
                await message.reply_text(t("error.not_found", language=language))
                return
            await message.reply_text(
                t("admin.payments.approve_prompt", language=language, payment=item.public_payment_id, order=item.public_order_id, amount=_money(item.amount, item.currency), method=item.payment_method),
                reply_markup=admin_approval_confirmation_keyboard(item.public_payment_id, language),
            )
            return
        if len(parts) == 4 and parts[2] == "approve_confirm":
            result = await service.approve(actor_telegram_id=actor_id, public_payment_id=parts[3], request_id=f"tg:{actor_id}:{parts[3]}")
            await _render_decision(message, result, language)
            return
        if len(parts) == 4 and parts[2] == "reject":
            await message.reply_text(t("admin.payments.reject", language=language), reply_markup=admin_rejection_reasons_keyboard(parts[3], language))
            return
        if len(parts) == 5 and parts[2] == "reject_reason":
            reason_code, payment_id = parts[3], parts[4]
            if reason_code == "other":
                context.user_data[_ADMIN_REVIEW_KEY] = {"admin_id": actor_id, "payment_id": payment_id, "stage": "custom_reason", "started_at": datetime.utcnow().isoformat()}
                await message.reply_text(t("admin.payments.enter_custom_reason", language=language, payment=payment_id), reply_markup=ForceReply(selective=True))
                return
            reason = t(f"admin.payments.reason_{reason_code}", language=language)
            context.user_data[_ADMIN_REVIEW_KEY] = {"admin_id": actor_id, "payment_id": payment_id, "stage": "confirm_rejection", "reason": reason}
            await message.reply_text(t("admin.payments.reject_prompt", language=language, payment=payment_id, reason=reason), reply_markup=admin_rejection_confirmation_keyboard(payment_id, language))
            return
        if len(parts) == 4 and parts[2] == "reject_confirm":
            state = context.user_data.get(_ADMIN_REVIEW_KEY) or {}
            if state.get("admin_id") != actor_id or state.get("payment_id") != parts[3] or not state.get("reason"):
                await message.reply_text(t("admin.payments.invalid_state", language=language))
                return
            result = await service.reject(actor_telegram_id=actor_id, public_payment_id=parts[3], reason=state["reason"], request_id=f"tg:{actor_id}:{parts[3]}")
            context.user_data.pop(_ADMIN_REVIEW_KEY, None)
            await _render_decision(message, result, language)
            return
    except (TypeError, ValueError):
        await message.reply_text(t("order.invalid_callback", language=language))


async def _render_decision(message, result, language: str) -> None:
    if result.is_success:
        decision = result.unwrap()
        if decision.already_decided:
            await message.reply_text(t("admin.payments.already_decided", language=language, status=decision.status))
        else:
            await message.reply_text(t("admin.payments.decision_success", language=language, decision=decision.decision))
        return
    code = result.error.code if result.error else ""
    key = {
        "unauthorized": "admin.payments.unauthorized",
        "not_found": "error.not_found",
        "invalid_order_state": "admin.payments.invalid_state",
        "invalid_order": "admin.payments.invalid_state",
        "payment_conflict": "admin.payments.invalid_state",
        "amount_or_currency_mismatch": "admin.payments.invalid_state",
        "manual_method_unavailable": "admin.payments.invalid_state",
        "submitted_after_expiry": "admin.payments.invalid_state",
    }.get(code, "common.error")
    await message.reply_text(t(key, language=language))


async def admin_review_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    actor_id = _actor_id(update)
    state = context.user_data.get(_ADMIN_REVIEW_KEY) or {}
    if message is None or actor_id is None or state.get("stage") != "custom_reason" or state.get("admin_id") != actor_id:
        return
    user = context.user_data.get(PLATFORM_USER_KEY)
    if getattr(user, "role", None) != "admin":
        return
    language = _language(context)
    reason = " ".join((message.text or "").split())[:500]
    if not reason:
        await message.reply_text(t("admin.payments.enter_custom_reason", language=language, payment=state.get("payment_id", "")), reply_markup=ForceReply(selective=True))
        return
    state["reason"] = reason
    state["stage"] = "confirm_rejection"
    await message.reply_text(t("admin.payments.reject_prompt", language=language, payment=state["payment_id"], reason=reason), reply_markup=admin_rejection_confirmation_keyboard(state["payment_id"], language))


async def admin_review_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.get(_ADMIN_REVIEW_KEY) or {}
    if not state:
        return
    if state.get("admin_id") != _actor_id(update):
        return
    context.user_data.pop(_ADMIN_REVIEW_KEY, None)
    if update.effective_message:
        await update.effective_message.reply_text(t("admin.payments.keep_reviewing", language=_language(context)))


def register(application: Application) -> None:
    application.add_handler(CommandHandler("admin", admin_panel), group=7)
    from app.handlers.admin_referral import register as register_admin_referral
    register_admin_referral(application)
    from app.handlers.admin_missions import register as register_admin_missions
    register_admin_missions(application)
    from app.handlers.admin_promo import register as register_admin_promo
    register_admin_promo(application)
    from app.handlers.admin_growth import register as register_admin_growth
    register_admin_growth(application)
    from app.handlers.admin_health import register as register_admin_health
    register_admin_health(application)
    from app.handlers.admin_jobs import register as register_admin_jobs
    register_admin_jobs(application)
    from app.handlers.admin_backup import register as register_admin_backup
    register_admin_backup(application)
    from app.handlers.admin_security import register as register_admin_security
    register_admin_security(application)
    application.add_handler(CommandHandler("cancel", admin_review_cancel), group=7)
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, admin_review_text), group=7)
    application.add_handler(
        CallbackQueryHandler(admin_payments_callback, pattern=r"^admin:(?:home|payments(?::(?:pending|approved|rejected):\d+)?|payments:(?:view|proof|approve|approve_confirm|reject|reject_confirm):[^:]+|payments:reject_reason:[^:]+:[^:]+)$"),
        group=7,
    )
    logger.debug("Phase 2.4 admin payment review handlers registered")
