"""Phase 1.5 My Keys customer handlers."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.handlers.base import log_handler
from app.handlers.customer_navigation import _get_user, _is_customer_surface, _language
from app.keyboards.customer_keys import (
    empty_keys_keyboard,
    key_details_keyboard,
    key_list_keyboard,
    key_subpage_keyboard,
)
from app.services.customer_key_service import CustomerKeyService
from app.services.free_trial_claim_service import FreeTrialClaimService
from locales.translator import t

logger = logging.getLogger(__name__)

_GB = 1024 ** 3


def _service(context: ContextTypes.DEFAULT_TYPE) -> CustomerKeyService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(CustomerKeyService)


def _fmt_gb(value: int | None, language: str) -> str:
    if value is None:
        return t("common.not_available", language=language)
    gb = max(value, 0) / _GB
    return f"{gb:.2f}".rstrip("0").rstrip(".") + " GB"


def _fmt_date(value: datetime | None, language: str) -> str:
    if value is None:
        return t("common.not_available", language=language)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _status(status: str, language: str) -> str:
    icons = {
        "active": "🟢",
        "pending": "🟡",
        "renewing": "🔄",
        "suspended": "🟠",
        "expired": "🔴",
        "revoked": "⛔",
    }
    key = f"keys.status.{status}"
    return f"{icons.get(status, '⚪')} {t(key, language=language)}"


def _type(key_type: str, language: str) -> str:
    icons = {
        "paid": "💎",
        "free_trial": "🎁",
        "promotion": "🎉",
        "reward": "🏆",
        "vip": "👑",
    }
    return f"{icons.get(key_type, '🔑')} {t(f'keys.type.{key_type}', language=language)}"


def _summary(item, language: str) -> str:
    return "\n".join([
        f"🔑 #{item.key_id} · {_type(item.key_type, language)}",
        f"{t('keys.package', language=language)}: {item.package_name or t('keys.unknown_package', language=language)}",
        f"{t('keys.server', language=language)}: {item.server_name or item.country or t('common.not_available', language=language)}",
        f"{t('keys.status', language=language)}: {_status(item.status, language)}",
        f"{t('keys.remaining', language=language)}: {_fmt_gb(item.remaining_bytes, language)}",
        f"{t('keys.expires', language=language)}: {_fmt_date(item.expires_at, language)}",
    ])


def _claim_service(context: ContextTypes.DEFAULT_TYPE) -> FreeTrialClaimService | None:
    registry = context.bot_data.get("registry")
    return None if registry is None else registry.get_or_none(FreeTrialClaimService)

async def _show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> None:
    user = _get_user(context)
    message = update.effective_message
    svc = _service(context)
    if not _is_customer_surface(user) or message is None:
        return
    language = _language(user)
    if svc is None:
        await message.reply_text(t("common.error", language=language))
        return

    result = await svc.list_customer_keys(user.telegram_id, page=page, page_size=5)
    if not result.items:
        await message.reply_text(
            t("keys.empty", language=language),
            reply_markup=empty_keys_keyboard(language),
        )
        return

    text = t("keys.title", language=language) + "\n\n" + "\n\n".join(
        _summary(item, language) for item in result.items
    )
    await message.reply_text(text, reply_markup=key_list_keyboard(result, language))


async def _show_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, key_id: int) -> None:
    user = _get_user(context)
    message = update.effective_message
    svc = _service(context)
    if not _is_customer_surface(user) or message is None:
        return
    language = _language(user)
    detail = None if svc is None else await svc.get_customer_key(user.telegram_id, key_id)
    if detail is None:
        logger.info("Owner-scoped VPN key lookup denied/not-found key_id=%s", key_id)
        await message.reply_text(t("keys.not_found", language=language))
        return

    lines = [
        t("keys.details_title", language=language),
        "",
        f"{t('keys.type_label', language=language)}: {_type(detail.key_type, language)}",
        f"{t('keys.package', language=language)}: {detail.package_name or t('keys.unknown_package', language=language)}",
        f"{t('keys.server', language=language)}: {detail.server_name or t('common.not_available', language=language)}",
        f"{t('keys.country', language=language)}: {detail.country or t('common.not_available', language=language)}",
        f"{t('keys.status', language=language)}: {_status(detail.status, language)}",
        f"{t('keys.total', language=language)}: {_fmt_gb(detail.data_limit_bytes, language)}",
        f"{t('keys.used', language=language)}: {_fmt_gb(detail.used_bytes, language)}",
        f"{t('keys.remaining', language=language)}: {_fmt_gb(detail.remaining_bytes, language)}",
        f"{t('keys.created', language=language)}: {_fmt_date(detail.created_at, language)}",
        f"{t('keys.expires', language=language)}: {_fmt_date(detail.expires_at, language)}",
        f"{t('keys.device_limit', language=language)}: {detail.device_limit if detail.device_limit is not None else t('common.not_available', language=language)}",
    ]
    await message.reply_text("\n".join(lines), reply_markup=key_details_keyboard(detail, language))


def _labels() -> set[str]:
    return {t("menu.my_keys", language=lang) for lang in ("en", "my")}


_LABELS = _labels()
_PATTERN = r"^(?:" + "|".join(re.escape(x) for x in _LABELS) + r")$"


@log_handler
async def my_keys_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_list(update, context, 1)


@log_handler
async def key_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = _get_user(context)
    if query is None or not _is_customer_surface(user):
        return
    await query.answer()

    language = _language(user)
    data = query.data or ""
    svc = _service(context)
    if svc is None:
        if query.message:
            await query.message.reply_text(t("common.error", language=language))
        return

    try:
        if data.startswith("key:page:"):
            page = max(1, int(data.rsplit(":", 1)[1]))
            await _show_list(update, context, page)
            return

        if data.startswith("key:view:"):
            key_id = int(data.rsplit(":", 1)[1])
            if key_id <= 0:
                raise ValueError
            await _show_detail(update, context, key_id)
            return

        if data.startswith("key:usage:"):
            key_id = int(data.rsplit(":", 1)[1])
            usage = await svc.get_usage_summary(user.telegram_id, key_id)
            if usage is None:
                if query.message:
                    await query.message.reply_text(t("keys.not_found", language=language))
                return
            percentage = (
                t("common.not_available", language=language)
                if usage.percentage is None
                else f"{usage.percentage:g}%"
            )
            text = "\n".join([
                t("keys.usage_title", language=language),
                "",
                f"{t('keys.total', language=language)}: {_fmt_gb(usage.data_limit_bytes, language)}",
                f"{t('keys.used', language=language)}: {_fmt_gb(usage.used_bytes, language)}",
                f"{t('keys.remaining', language=language)}: {_fmt_gb(usage.remaining_bytes, language)}",
                f"{t('keys.percentage', language=language)}: {percentage}",
                f"{t('keys.last_synced', language=language)}: {_fmt_date(usage.last_synced_at, language)}",
                f"{t('keys.expires', language=language)}: {_fmt_date(usage.expires_at, language)}",
            ])
            if query.message:
                await query.message.reply_text(text, reply_markup=key_subpage_keyboard(key_id, language))
            return

        if data.startswith("key:connect:"):
            key_id = int(data.rsplit(":", 1)[1])
            connection = await svc.get_connection_info(user.telegram_id, key_id)
            if connection is None:
                if query.message:
                    await query.message.reply_text(t("keys.connection_unavailable", language=language))
                return
            # Never log connection.access_url.
            text = "\n".join([
                t("keys.connection_title", language=language),
                "",
                f"{t('keys.server', language=language)}: {connection.server_name or connection.country or t('common.not_available', language=language)}",
                f"{t('keys.status', language=language)}: {_status(connection.status, language)}",
                "",
                t("keys.access_key", language=language) + ":",
                connection.access_url,
                "",
                t("keys.copy_hint", language=language),
            ])
            if query.message:
                await query.message.reply_text(text, reply_markup=key_subpage_keyboard(key_id, language))
            return

        if data.startswith("key:renew:"):
            key_id = int(data.rsplit(":", 1)[1])
            detail = await svc.get_customer_key(user.telegram_id, key_id)
            if detail is None:
                if query.message:
                    await query.message.reply_text(t("keys.not_found", language=language))
                return
            if not await svc.can_renew(user.telegram_id, key_id):
                if query.message:
                    await query.message.reply_text(t("keys.renew_unavailable", language=language))
                return
            if query.message:
                await query.message.reply_text(
                    t("keys.renew_placeholder", language=language),
                    reply_markup=key_subpage_keyboard(key_id, language),
                )
            return

        if data == "key:trial-placeholder":
            claim_svc = _claim_service(context)
            if claim_svc is None or query.message is None:
                if query.message: await query.message.reply_text(t("common.error", language=language))
                return
            claim_key = f"telegram:{user.telegram_id}:free:{datetime.now().strftime("%Y%m%d%H%M%S")}:{query.id}"
            result = await claim_svc.accept_claim(user_id=user.id, package_id=0, idempotency_key=claim_key)
            if result.is_success:
                await query.message.reply_text(t("free_trial.accepted", language=language))
            else:
                code = result.error.code if result.error else "disabled"
                key = {"daily_allowance_exhausted":"free_trial.daily_allowance_exhausted", "no_extra_entitlement":"free_trial.no_extra_entitlement", "membership_required":"free_trial.membership_required", "free_trial_disabled":"free_trial.disabled"}.get(code, "common.error")
                await query.message.reply_text(t(key, language=language))
            return

    except (TypeError, ValueError):
        logger.info("Malformed customer-key callback: %r", data)
        if query.message:
            await query.message.reply_text(t("keys.invalid_callback", language=language))


def register(application: Application) -> None:
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(_PATTERN), my_keys_message),
        group=7,
    )
    application.add_handler(
        CallbackQueryHandler(
            key_callback,
            pattern=r"^key:(?:page:\d+|view:\d+|usage:\d+|connect:\d+|renew:\d+|trial-placeholder)$",
        ),
        group=7,
    )
    logger.debug("Phase 1.5 customer key handlers registered")
