"""
Main menu keyboards.

Provides the primary navigation keyboard shown after /start.
Different keyboards are returned based on the user's role.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.models.enums import UserRole


def build_main_menu(role: UserRole = UserRole.CUSTOMER) -> InlineKeyboardMarkup:
    """
    Build the main navigation menu for the given user role.

    Args:
        role: The current user's role (determines which buttons are shown).

    Returns:
        InlineKeyboardMarkup ready to pass to message.reply_text().

    TODO (Phase 1): populate button labels from the i18n translation system.
    TODO (Phase 1): add conditional admin row when role == UserRole.ADMIN.
    """
    customer_buttons = [
        [InlineKeyboardButton("📦 Packages", callback_data="menu:packages")],
        [InlineKeyboardButton("🔑 My Keys", callback_data="menu:my_keys")],
        [InlineKeyboardButton("💰 Wallet", callback_data="menu:wallet")],
        [InlineKeyboardButton("🌐 Language", callback_data="menu:language")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu:help")],
    ]

    admin_row = [InlineKeyboardButton("🛠 Admin Panel", callback_data="menu:admin")]

    buttons = customer_buttons
    if role == UserRole.ADMIN:
        buttons = [admin_row] + customer_buttons

    return InlineKeyboardMarkup(buttons)


def build_language_selector() -> InlineKeyboardMarkup:
    """
    Build a language selection keyboard.

    Returns:
        InlineKeyboardMarkup with one button per supported language.
    """
    buttons = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")],
        [InlineKeyboardButton("🇲🇲 မြန်မာဘာသာ", callback_data="lang:my")],
    ]
    return InlineKeyboardMarkup(buttons)
