"""Inline keyboards for the Phase 2.4 admin payment review workflow."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from locales.translator import t


def admin_payment_menu_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.payments.pending", language=language), callback_data="admin:payments:pending:1")],
        [InlineKeyboardButton(t("admin.payments.approved", language=language), callback_data="admin:payments:approved:1")],
        [InlineKeyboardButton(t("admin.payments.rejected", language=language), callback_data="admin:payments:rejected:1")],
        [InlineKeyboardButton(t("admin.servers.menu", language=language), callback_data="admin:servers:menu")],
        [InlineKeyboardButton(t("admin.growth.menu", language=language), callback_data="admin:growth:menu")],
        [InlineKeyboardButton(t("admin.health.menu", language=language), callback_data="admin:health:menu")],
        [InlineKeyboardButton(t("admin.jobs.menu", language=language), callback_data="admin:jobs:menu")],
        [InlineKeyboardButton(t("admin.backup.menu", language=language), callback_data="admin:backup:menu")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:home")],
    ])


def admin_pending_queue_keyboard(page: int, has_previous: bool, has_next: bool, language: str, status: str = "pending", payment_ids: list[str] | None = None) -> InlineKeyboardMarkup:
    rows = []
    for payment_id in payment_ids or []:
        rows.append([InlineKeyboardButton(f"🔍 {payment_id}", callback_data=f"admin:payments:view:{payment_id}")])
    if has_previous or has_next:
        pager = []
        if has_previous:
            pager.append(InlineKeyboardButton(t("nav.previous", language=language), callback_data=f"admin:payments:{status}:{max(1, page - 1)}"))
        if has_next:
            pager.append(InlineKeyboardButton(t("nav.next", language=language), callback_data=f"admin:payments:{status}:{page + 1}"))
        rows.append(pager)
    rows.extend([
        [InlineKeyboardButton(t("admin.payments.refresh", language=language), callback_data=f"admin:payments:{status}:{page}")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:payments")],
    ])
    return InlineKeyboardMarkup(rows)


def admin_review_keyboard(public_payment_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.payments.view_proof", language=language), callback_data=f"admin:payments:proof:{public_payment_id}")],
        [InlineKeyboardButton(t("admin.payments.approve", language=language), callback_data=f"admin:payments:approve:{public_payment_id}")],
        [InlineKeyboardButton(t("admin.payments.reject", language=language), callback_data=f"admin:payments:reject:{public_payment_id}")],
        [InlineKeyboardButton(t("admin.payments.back_queue", language=language), callback_data="admin:payments:pending:1")],
    ])


def admin_approval_confirmation_keyboard(public_payment_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.payments.confirm_approve", language=language), callback_data=f"admin:payments:approve_confirm:{public_payment_id}")],
        [InlineKeyboardButton(t("admin.payments.keep_reviewing", language=language), callback_data=f"admin:payments:view:{public_payment_id}")],
    ])


def admin_rejection_reasons_keyboard(public_payment_id: str, language: str) -> InlineKeyboardMarkup:
    reasons = (
        ("invalid_proof", "admin.payments.reason_invalid_proof"),
        ("wrong_amount", "admin.payments.reason_wrong_amount"),
        ("transaction_not_found", "admin.payments.reason_transaction_not_found"),
        ("duplicate_proof", "admin.payments.reason_duplicate_proof"),
        ("wrong_reference", "admin.payments.reason_wrong_reference"),
        ("payment_not_received", "admin.payments.reason_payment_not_received"),
        ("order_expired", "admin.payments.reason_order_expired"),
        ("other", "admin.payments.reason_other"),
    )
    rows = [[InlineKeyboardButton(t(label, language=language), callback_data=f"admin:payments:reject_reason:{reason}:{public_payment_id}")] for reason, label in reasons]
    rows.append([InlineKeyboardButton(t("admin.payments.keep_reviewing", language=language), callback_data=f"admin:payments:view:{public_payment_id}")])
    return InlineKeyboardMarkup(rows)


def admin_rejection_confirmation_keyboard(public_payment_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.payments.confirm_reject", language=language), callback_data=f"admin:payments:reject_confirm:{public_payment_id}")],
        [InlineKeyboardButton(t("admin.payments.keep_reviewing", language=language), callback_data=f"admin:payments:view:{public_payment_id}")],
    ])
