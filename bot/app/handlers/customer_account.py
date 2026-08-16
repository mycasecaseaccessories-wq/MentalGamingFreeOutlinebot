"""Phase 1.3 customer Profile, Wallet and Support handlers."""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import log_handler
from app.handlers.customer_navigation import _get_user, _is_customer_surface, _language
from app.keyboards.customer_account import (
    profile_keyboard, wallet_keyboard, wallet_subpage_keyboard,
    transaction_keyboard, support_keyboard, support_subpage_keyboard,
)
from app.keyboards.language import build_onboarding_language_keyboard
from app.models.customer_account import TransactionSummary
from app.services.profile_service import ProfileService
from app.services.wallet_service import WalletService
from app.services.support_service import SupportService
from app.services.history_service import HistoryService
from app.keyboards.history import history_detail_keyboard, history_list_keyboard
from app.models.history import OrderHistoryItem, PaymentHistoryItem
from app.utils.customer_formatters import (
    format_boolean, format_datetime, format_enum, format_money,
    format_optional, format_username,
)
from locales.translator import t

logger = logging.getLogger(__name__)


def _service(context, cls):
    registry = context.bot_data.get("registry")
    if registry is None:
        return None
    return registry.get_or_none(cls)


def _labels() -> dict[str, str]:
    result = {}
    for lang in ("en", "my"):
        result[t("menu.profile", language=lang)] = "profile"
        result[t("menu.wallet", language=lang)] = "wallet"
        result[t("menu.support", language=lang)] = "support"
        result[t("menu.orders", language=lang)] = "orders"
        result[t("menu.payments", language=lang)] = "payments"
    return result


_LABELS = _labels()
_PATTERN = r"^(?:" + "|".join(re.escape(x) for x in _LABELS) + r")$"


async def _show_profile(update, context):
    user = _get_user(context); lang = _language(user)
    svc = _service(context, ProfileService)
    if not user or not svc or update.effective_message is None:
        return
    data = await svc.get_customer_profile(user.telegram_id)
    if data is None:
        await update.effective_message.reply_text(t("error.not_found", language=lang)); return
    not_set = t("common.not_set", language=lang)
    enabled = t("common.enabled", language=lang); disabled = t("common.disabled", language=lang)
    text = "\n".join([
        t("profile.phase13_title", language=lang),
        "",
        t("profile.telegram_id", language=lang, value=data.telegram_id),
        t("profile.username13", language=lang, value=format_username(data.username, not_set)),
        t("profile.first_name", language=lang, value=format_optional(data.first_name, not_set)),
        t("profile.last_name", language=lang, value=format_optional(data.last_name, not_set)),
        t("profile.role13", language=lang, value=format_enum(data.role)),
        t("profile.status13", language=lang, value=format_enum(data.status)),
        t("profile.language13", language=lang, value=data.language.upper()),
        t("profile.joined", language=lang, value=format_datetime(data.created_at, not_set)),
        t("profile.last_active13", language=lang, value=format_datetime(data.last_active, not_set)),
        t("profile.currency", language=lang, value=data.preferred_currency),
        t("profile.notifications", language=lang, value=format_boolean(data.notification_enabled, enabled, disabled)),
        t("profile.broadcasts", language=lang, value=format_boolean(data.broadcast_enabled, enabled, disabled)),
    ])
    await update.effective_message.reply_text(text, reply_markup=profile_keyboard(lang))


async def _show_wallet(update, context):
    user = _get_user(context); lang = _language(user)
    svc = _service(context, WalletService)
    if not user or not svc or update.effective_message is None: return
    currency = getattr(context.bot_data.get("settings"), "default_currency", "MMK")
    data = await svc.get_wallet_summary(user.telegram_id, currency=currency)
    text = f"{t('wallet.title13', language=lang)}\n\n{t('wallet.balance', language=lang, value=format_money(data.balance, data.currency))}"
    if data.is_frozen:
        text += "\n" + t("wallet.frozen", language=lang)
    await update.effective_message.reply_text(text, reply_markup=wallet_keyboard(lang))


def _history_service(context):
    return _service(context, HistoryService)


def _history_date(value) -> str:
    return format_datetime(value, "—")


_STATUS_KEYS = {"waiting_payment", "awaiting_approval", "paid", "completed", "cancelled", "expired", "refunded", "pending_review", "approved", "rejected"}


def _status_text(status: str | None, lang: str) -> str:
    if not status:
        return "—"
    return t(f"order.{status}", language=lang) if status in _STATUS_KEYS else status.replace("_", " ").title()


def _format_order_history(item: OrderHistoryItem, lang: str) -> str:
    return t("history.order_item", language=lang, order=item.public_order_id, package=item.package_name, amount=format_money(item.amount, item.currency), status=_status_text(item.status, lang), date=_history_date(item.created_at))


def _format_payment_history(item: PaymentHistoryItem, lang: str) -> str:
    status = _status_text(item.status, lang)
    reason = t("history.rejection_reason", language=lang, reason=item.rejection_reason) if item.rejection_reason else ""
    return t("history.payment_item", language=lang, type=item.payment_type.title(), order=item.order_public_id or "—", amount=format_money(item.amount, item.currency), status=status, reference=item.reference or "—", date=_history_date(item.created_at), reason=reason)


async def _show_orders(update, context, *, page: int = 1):
    user = _get_user(context); lang = _language(user); svc = _history_service(context); message = update.effective_message
    if not user or not svc or message is None: return
    result = await svc.list_orders(user.telegram_id, page=page)
    if not result.items:
        await message.reply_text(t("history.orders_empty", language=lang), reply_markup=history_list_keyboard(lang, kind="orders", page=1, has_previous=False, has_next=False)); return
    text = t("history.orders_title", language=lang, page=result.page) + "\n\n" + "\n\n".join(_format_order_history(item, lang) for item in result.items)
    await message.reply_text(text, reply_markup=history_list_keyboard(lang, kind="orders", page=result.page, has_previous=result.has_previous, has_next=result.has_next, ids=[item.public_order_id for item in result.items]))


async def _show_order_detail(update, context, public_order_id: str):
    user = _get_user(context); lang = _language(user); svc = _history_service(context); message = update.effective_message
    if not user or not svc or message is None: return
    item = await svc.get_order(user.telegram_id, public_order_id)
    if item is None:
        await message.reply_text(t("history.not_found", language=lang)); return
    text = t("history.details", language=lang, order=item.public_order_id, package=item.package_name, data=f"{item.data_limit_gb or '—'} GB", duration=f"{item.duration_days or '—'} days", devices=item.device_limit or "—", amount=format_money(item.amount, item.currency), currency=item.currency, order_status=_status_text(item.status, lang), payment_status=_status_text(item.payment_status, lang), method=item.payment_method or "—", reference=item.payment_reference or "—", created=_history_date(item.created_at), paid=_history_date(item.paid_at), expires=_history_date(item.expires_at))
    await message.reply_text(text, reply_markup=history_detail_keyboard(lang, kind="orders"))


async def _show_payments(update, context, *, page: int = 1):
    user = _get_user(context); lang = _language(user); svc = _history_service(context); message = update.effective_message
    if not user or not svc or message is None: return
    result = await svc.list_payments(user.telegram_id, page=page)
    if not result.items:
        await message.reply_text(t("history.payments_empty", language=lang), reply_markup=history_list_keyboard(lang, kind="payments", page=1, has_previous=False, has_next=False)); return
    text = t("history.payments_title", language=lang, page=result.page) + "\n\n" + "\n\n".join(_format_payment_history(item, lang) for item in result.items)
    await message.reply_text(text, reply_markup=history_list_keyboard(lang, kind="payments", page=result.page, has_previous=result.has_previous, has_next=result.has_next))


async def _show_support(update, context):
    user = _get_user(context); lang = _language(user)
    svc = _service(context, SupportService)
    if not user or not svc or update.effective_message is None: return
    info = await svc.get_support_info(context.bot_data.get("settings"))
    if info.username:
        contact = f"@{info.username}"
        body = t("support.body", language=lang, contact=contact)
    else:
        body = t("support.unavailable", language=lang)
    if info.hours: body += "\n" + t("support.hours", language=lang, value=info.hours)
    if info.email: body += "\n" + t("support.email", language=lang, value=info.email)
    if info.message: body += "\n\n" + info.message
    await update.effective_message.reply_text(
        f"{t('support.title13', language=lang)}\n\n{body}",
        reply_markup=support_keyboard(lang, info.username),
    )


@log_handler
async def account_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _get_user(context)
    msg = update.effective_message
    if not _is_customer_surface(user) or msg is None or not msg.text: return
    dest = _LABELS.get(msg.text.strip())
    if dest == "profile": await _show_profile(update, context)
    elif dest == "wallet": await _show_wallet(update, context)
    elif dest == "support": await _show_support(update, context)
    elif dest == "orders": await _show_orders(update, context)
    elif dest == "payments": await _show_payments(update, context)


def _format_tx(tx: TransactionSummary, lang: str) -> str:
    not_set = t("common.not_set", language=lang)
    return "\n".join([
        f"• {format_enum(tx.type)} — {format_money(tx.amount, tx.currency)}",
        f"  {format_datetime(tx.created_at, not_set)}",
        f"  {format_optional(tx.note or tx.reference, not_set)}",
    ])


@log_handler
async def account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query; user = _get_user(context)
    if q is None or not _is_customer_surface(user): return
    await q.answer(); lang = _language(user); data = q.data or ""
    if data == "acct:profile":
        await _show_profile(update, context); return
    if data == "acct:profile:language":
        await q.message.reply_text(t("language.select_prompt", language=lang), reply_markup=build_onboarding_language_keyboard()); return
    if data == "acct:profile:notifications":
        svc = _service(context, ProfileService); p = await svc.get_customer_profile(user.telegram_id)
        value = t("common.enabled" if p and p.notification_enabled else "common.disabled", language=lang)
        await q.answer(t("profile.notifications_state", language=lang, value=value), show_alert=True); return
    if data == "acct:wallet":
        await _show_wallet(update, context); return
    if data == "acct:wallet:topup":
        await q.message.reply_text(t("wallet.topup_placeholder", language=lang), reply_markup=wallet_subpage_keyboard(lang)); return
    if data.startswith("history:orders:page:"):
        try: page = max(1, int(data.rsplit(":", 1)[1]))
        except ValueError: page = 1
        await _show_orders(update, context, page=page); return
    if data.startswith("history:orders:detail:"):
        await _show_order_detail(update, context, data.split(":", 3)[3]); return
    if data.startswith("history:payments:page:"):
        try: page = max(1, int(data.rsplit(":", 1)[1]))
        except ValueError: page = 1
        await _show_payments(update, context, page=page); return
    if data.startswith("acct:wallet:tx:"):
        try: page = max(1, int(data.rsplit(":", 1)[1]))
        except ValueError: page = 1
        svc = _service(context, WalletService)
        currency = getattr(context.bot_data.get("settings"), "default_currency", "MMK")
        result = await svc.get_transaction_history(user.telegram_id, page=page, page_size=5, currency=currency)
        if not result.items:
            text = t("wallet.no_transactions", language=lang)
        else:
            text = t("wallet.transactions_title", language=lang) + "\n\n" + "\n\n".join(_format_tx(x, lang) for x in result.items)
        await q.message.reply_text(text, reply_markup=transaction_keyboard(lang, page=result.page, has_previous=result.has_previous, has_next=result.has_next)); return
    if data == "acct:support":
        await _show_support(update, context); return
    if data == "acct:support:faq":
        await q.message.reply_text(t("support.faq_body", language=lang), reply_markup=support_subpage_keyboard(lang)); return


def register(application: Application) -> None:
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(_PATTERN), account_menu_message),
        group=9,
    )
    application.add_handler(
        CallbackQueryHandler(account_callback, pattern=r"^acct:"),
        group=9,
    )
    logger.debug("Phase 1.3 customer account handlers registered")
