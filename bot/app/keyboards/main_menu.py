"""Main navigation keyboards.

Phase 1.2 introduces the persistent customer ReplyKeyboard while preserving
the legacy ``build_main_menu`` API used by earlier phases.
"""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.models.enums import UserRole
from locales.translator import t


def build_customer_main_menu(language: str = "en") -> ReplyKeyboardMarkup:
    """Return the persistent localized customer main menu."""
    keyboard = [
        [
            KeyboardButton(t("menu.buy_vpn", language=language)),
            KeyboardButton(t("menu.free_trial", language=language)),
        ],
        [
            KeyboardButton(t("menu.my_keys", language=language)),
            KeyboardButton(t("menu.wallet", language=language)),
        ],
        [
            KeyboardButton(t("menu.profile", language=language)),
            KeyboardButton(t("menu.support", language=language)),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=t("menu.input_hint", language=language),
    )


def build_customer_page_navigation(language: str = "en") -> InlineKeyboardMarkup:
    """Return lightweight navigation controls for placeholder feature pages."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("nav.home", language=language),
                    callback_data="nav:home",
                )
            ]
        ]
    )


def build_main_menu(role: UserRole = UserRole.CUSTOMER) -> InlineKeyboardMarkup:
    """Backward-compatible legacy inline menu.

    New customer flows should use :func:`build_customer_main_menu`.
    """
    customer_buttons = [
        [InlineKeyboardButton("📦 Packages", callback_data="menu:packages")],
        [InlineKeyboardButton("🔑 My Keys", callback_data="menu:my_keys")],
        [InlineKeyboardButton("💰 Wallet", callback_data="menu:wallet")],
        [InlineKeyboardButton("🌐 Language", callback_data="menu:language")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu:help")],
    ]
    if role == UserRole.ADMIN:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛠 Admin Panel", callback_data="menu:admin")]]
            + customer_buttons
        )
    return InlineKeyboardMarkup(customer_buttons)


def build_language_selector() -> InlineKeyboardMarkup:
    """Backward-compatible language selection keyboard."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
            [InlineKeyboardButton("🇲🇲 မြန်မာဘာသာ", callback_data="lang:my")],
        ]
    )
