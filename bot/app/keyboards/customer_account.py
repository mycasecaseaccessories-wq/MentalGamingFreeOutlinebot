"""Customer account reply keyboard."""

from telegram import ReplyKeyboardMarkup


def build_customer_menu(language: str = "en") -> ReplyKeyboardMarkup:
    labels = (
        ["🛒 Buy VPN", "🎁 Free Trial"],
        ["🔑 My Keys", "💰 Wallet"],
        ["👤 Profile", "🎫 Support"],
    )
    if language == "my":
        labels = (
            ["🛒 VPN ဝယ်ရန်", "🎁 အခမဲ့စမ်းသုံးရန်"],
            ["🔑 My Keys", "💰 Wallet"],
            ["👤 ကိုယ်ရေးအချက်အလက်", "🎫 အကူအညီ"],
        )
    return ReplyKeyboardMarkup(labels, resize_keyboard=True, is_persistent=True)