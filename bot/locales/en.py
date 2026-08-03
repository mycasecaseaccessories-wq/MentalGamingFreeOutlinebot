"""
English translations.

Keys use dot-notation: "section.key"
Values are plain strings; use {placeholder} for dynamic content.

This file is the source-of-truth for all translation keys.
Every key added here MUST have a corresponding entry in every other
language file (or the fallback mechanism will silently use English).
"""

TRANSLATIONS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────────────────
    "common.loading":       "⏳ Loading...",
    "common.error":         "⚠️ Something went wrong. Please try again.",
    "common.back":          "⬅️ Back",
    "common.cancel":        "❌ Cancel",
    "common.confirm":       "✅ Confirm",
    "common.yes":           "Yes",
    "common.no":            "No",

    # ── Welcome / onboarding ──────────────────────────────────────────────
    "welcome.greeting":     "👋 Welcome to Mental Outline VPN, {name}!",
    "welcome.choose_lang":  "Please choose your language:",

    # ── Main menu ─────────────────────────────────────────────────────────
    "menu.packages":        "📦 Packages",
    "menu.my_keys":         "🔑 My VPN Keys",
    "menu.wallet":          "💰 Wallet",
    "menu.language":        "🌐 Language",
    "menu.help":            "ℹ️ Help",
    "menu.admin":           "🛠 Admin Panel",

    # ── Errors ────────────────────────────────────────────────────────────
    "error.unauthorized":   "⛔ You do not have permission to do that.",
    "error.not_found":      "🔍 Not found.",
    "error.generic":        "⚠️ An unexpected error occurred. Our team has been notified.",

    # ── Placeholders (Phase 1+) ───────────────────────────────────────────
    "placeholder.coming_soon": "🚧 Coming soon! Stay tuned.",
}
