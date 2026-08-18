"""Inline keyboards for Phase 2.1 checkout and order screens."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from locales.translator import t


def build_checkout_keyboard(token: str, language: str, confirm_callback_data: str | None = None, cancel_callback_data: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.confirm", language=language), callback_data=confirm_callback_data or f"checkout:confirm:{token}")],
        [InlineKeyboardButton(t("order.cancel", language=language), callback_data=cancel_callback_data or f"checkout:cancel:{token}")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data="pkg:list:1")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_order_created_keyboard(public_order_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.choose_payment", language=language), callback_data=f"order:pay:{public_order_id}")],
        [InlineKeyboardButton(t("order.cancel", language=language), callback_data=f"order:cancel:{public_order_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_wallet_payment_preview_keyboard(public_order_id: str, language: str, confirm_callback_data: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.wallet_confirm", language=language), callback_data=confirm_callback_data or f"wallet:confirm:{public_order_id}")],
        [InlineKeyboardButton(t("order.wallet_cancel", language=language), callback_data=f"wallet:cancel:{public_order_id}")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data=f"order:pay:{public_order_id}")],
    ])


def build_wallet_payment_result_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("package.catalog_title", language=language), callback_data="pkg:list:1")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_payment_methods_keyboard(public_order_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.wallet", language=language), callback_data=f"order:pay:wallet:{public_order_id}")],
        [InlineKeyboardButton(t("order.manual", language=language), callback_data=f"order:pay:manual:{public_order_id}")],
        [InlineKeyboardButton(t("common.back", language=language), callback_data=f"order:view:{public_order_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_manual_payment_methods_keyboard(public_order_id: str, methods, language: str) -> InlineKeyboardMarkup:
    rows = []
    for method in methods:
        rows.append([
            InlineKeyboardButton(
                method.name,
                callback_data=f"manual:method:{method.method_id}:{public_order_id}",
            )
        ])
    rows.extend([
        [InlineKeyboardButton(t("common.back", language=language), callback_data=f"order:pay:{public_order_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
    return InlineKeyboardMarkup(rows)


def build_manual_payment_instruction_keyboard(public_order_id: str, method_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.manual_submit_reference", language=language), callback_data=f"manual:submit:{method_id}:{public_order_id}")],
        [InlineKeyboardButton(t("order.manual_back_methods", language=language), callback_data=f"order:pay:manual:{public_order_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_manual_payment_waiting_keyboard(public_order_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.view", language=language), callback_data=f"order:view:{public_order_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_order_details_keyboard(public_order_id: str, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.choose_payment", language=language), callback_data=f"order:pay:{public_order_id}")],
        [InlineKeyboardButton(t("order.cancel", language=language), callback_data=f"order:cancel:{public_order_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def build_cancel_confirmation_keyboard(public_order_id: str, language: str, confirm_callback_data: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("order.confirm_cancel", language=language), callback_data=confirm_callback_data or f"order:cancel_confirm:{public_order_id}")],
        [InlineKeyboardButton(t("order.keep", language=language), callback_data=f"order:cancel_keep:{public_order_id}")],
    ])


def build_cancelled_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("package.catalog_title", language=language), callback_data="pkg:list:1")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
