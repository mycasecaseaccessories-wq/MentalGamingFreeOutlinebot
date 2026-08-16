"""Admin Outline Setup keyboards; callbacks carry only opaque flow IDs."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from locales.translator import t


def outline_setup_methods_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.outline.api_url", language=language), callback_data="admin:outline:api_url")],
        [InlineKeyboardButton(t("admin.outline.ssh", language=language), callback_data="admin:outline:future:ssh")],
        [InlineKeyboardButton(t("admin.outline.auto", language=language), callback_data="admin:outline:future:auto")],
        [InlineKeyboardButton(t("admin.outline.manual", language=language), callback_data="admin:servers:add:manual")],
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="admin:servers:menu")],
    ])


def ssh_auth_keyboard(language: str, flow_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.outline.ssh_password", language=language), callback_data=f"admin:outline:ssh_auth:password:{flow_id}")],
        [InlineKeyboardButton(t("admin.outline.ssh_key", language=language), callback_data=f"admin:outline:ssh_auth:private_key:{flow_id}")],
        [InlineKeyboardButton(t("admin.outline.cancel", language=language), callback_data=f"admin:outline:cancel:{flow_id}")],
    ])


def ssh_test_keyboard(language: str, flow_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.outline.ssh_test", language=language), callback_data=f"admin:outline:ssh_test:{flow_id}")],
        [InlineKeyboardButton(t("admin.outline.cancel", language=language), callback_data=f"admin:outline:cancel:{flow_id}")],
    ])


def outline_not_found_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.outline.auto", language=language), callback_data="admin:outline:future:auto")],
        [InlineKeyboardButton(t("admin.outline.cancel", language=language), callback_data="admin:servers:menu")],
    ])


def outline_review_keyboard(language: str, flow_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("admin.outline.save_disabled", language=language), callback_data=f"admin:outline:save_disabled:{flow_id}")],
        [InlineKeyboardButton(t("admin.outline.save_enable", language=language), callback_data=f"admin:outline:save_enable:{flow_id}")],
        [InlineKeyboardButton(t("admin.outline.test_again", language=language), callback_data=f"admin:outline:test_again:{flow_id}")],
        [InlineKeyboardButton(t("admin.outline.cancel", language=language), callback_data=f"admin:outline:cancel:{flow_id}")],
    ])
