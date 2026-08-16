"""Language selection keyboard for Phase 1.1."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_onboarding_language_keyboard() -> InlineKeyboardMarkup:
    """Return the first-run language selector."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="onboarding:lang:my")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="onboarding:lang:en")],
        ]
    )
