"""Package catalogue inline keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_package_list_keyboard(package_ids: list[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"📦 Package #{package_id}",
                               callback_data=f"catalog:view:{package_id}")]
         for package_id in package_ids]
        + [[InlineKeyboardButton("⬅️ Main menu", callback_data="nav:home")]]
    )


def build_package_detail_keyboard(package_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Select package",
                                  callback_data=f"catalog:select:{package_id}")],
            [InlineKeyboardButton("⬅️ Packages", callback_data="nav:packages")],
        ]
    )