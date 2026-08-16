"""Inline keyboards for Phase 1.5 My Keys pages."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.customer_keys import CustomerKeyDetail, CustomerKeyPage
from locales.translator import t


def key_list_keyboard(page: CustomerKeyPage, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(f"🔍 #{item.key_id} · {item.package_name or t('keys.unknown_package', language=language)}",
                              callback_data=f"key:view:{item.key_id}")]
        for item in page.items
    ]
    pager: list[InlineKeyboardButton] = []
    if page.has_previous:
        pager.append(InlineKeyboardButton(
            t("nav.previous", language=language),
            callback_data=f"key:page:{page.page - 1}",
        ))
    if page.has_next:
        pager.append(InlineKeyboardButton(
            t("nav.next", language=language),
            callback_data=f"key:page:{page.page + 1}",
        ))
    if pager:
        rows.append(pager)
    rows.append([InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def empty_keys_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("menu.buy_vpn", language=language), callback_data="pkg:list:1")],
        [InlineKeyboardButton(t("menu.free_trial", language=language), callback_data="key:trial-placeholder")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def key_details_keyboard(detail: CustomerKeyDetail, language: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if detail.status == "active":
        rows.append([
            InlineKeyboardButton(t("keys.connect", language=language), callback_data=f"key:connect:{detail.key_id}"),
            InlineKeyboardButton(t("keys.usage", language=language), callback_data=f"key:usage:{detail.key_id}"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(t("keys.usage", language=language), callback_data=f"key:usage:{detail.key_id}")
        ])

    if detail.key_type != "free_trial" and detail.status in {"active", "expired", "suspended"}:
        rows.append([
            InlineKeyboardButton(t("keys.renew", language=language), callback_data=f"key:renew:{detail.key_id}")
        ])

    rows.extend([
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="key:page:1")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
    return InlineKeyboardMarkup(rows)


def key_subpage_keyboard(key_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("nav.back", language=language), callback_data=f"key:view:{key_id}")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
