"""Onboarding language keyboard."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_onboarding_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇬🇧 English", callback_data="onboarding:language:en")],
            [InlineKeyboardButton("🇲🇲 မြန်မာဘာသာ", callback_data="onboarding:language:my")],
        ]
    )