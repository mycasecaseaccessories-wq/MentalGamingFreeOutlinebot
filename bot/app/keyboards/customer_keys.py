"""My Keys inline keyboard builders."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_key_list_keyboard(key_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"🔑 Key #{key_id}", callback_data=f"keys:view:{key_id}")]
             for key_id in key_ids]
    rows.append([InlineKeyboardButton("🛒 Buy VPN", callback_data="nav:packages")])
    return InlineKeyboardMarkup(rows)


def build_key_detail_keyboard(key_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Usage", callback_data=f"keys:usage:{key_id}")],
            [InlineKeyboardButton("🔗 Connect", callback_data=f"keys:connect:{key_id}")],
            [InlineKeyboardButton("🔄 Renew", callback_data=f"keys:renew:{key_id}")],
            [InlineKeyboardButton("⬅️ Main menu", callback_data="nav:home")],
        ]
    )