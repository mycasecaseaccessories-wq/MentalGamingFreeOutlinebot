"""Inline keyboards for Phase 1.3 Profile, Wallet and Support pages."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from locales.translator import t


def profile_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("profile.language_button", language=language), callback_data="acct:profile:language"),
            InlineKeyboardButton(t("profile.notifications_button", language=language), callback_data="acct:profile:notifications"),
        ],
        [
            InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home"),
        ],
    ])


def wallet_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("wallet.topup", language=language), callback_data="acct:wallet:topup"),
            InlineKeyboardButton(t("wallet.transactions", language=language), callback_data="acct:wallet:tx:1"),
        ],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def wallet_subpage_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="acct:wallet")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])


def transaction_keyboard(
    language: str,
    *,
    page: int,
    has_previous: bool,
    has_next: bool,
) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    if has_previous:
        row.append(InlineKeyboardButton(t("nav.previous", language=language), callback_data=f"acct:wallet:tx:{page - 1}"))
    if has_next:
        row.append(InlineKeyboardButton(t("nav.next", language=language), callback_data=f"acct:wallet:tx:{page + 1}"))

    rows: list[list[InlineKeyboardButton]] = []
    if row:
        rows.append(row)
    rows.extend([
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="acct:wallet")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
    return InlineKeyboardMarkup(rows)


def support_keyboard(language: str, username: str | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if username:
        rows.append([
            InlineKeyboardButton(
                t("support.contact_button", language=language),
                url=f"https://t.me/{username.lstrip('@')}",
            )
        ])
    rows.append([InlineKeyboardButton(t("support.faq_button", language=language), callback_data="acct:support:faq")])
    rows.append([InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def support_subpage_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("nav.back", language=language), callback_data="acct:support")],
        [InlineKeyboardButton(t("nav.home", language=language), callback_data="nav:home")],
    ])
