"""
English (en) translations for the Mental Outline VPN Platform.

This package supersedes locales/en.py (kept for reference).
Keys follow dot-notation: "section.key" (e.g. "welcome.greeting").

Phase 0.4: Added auth, language-selection, status, and role keys.
"""

TRANSLATIONS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────────────────
    "common.loading":           "⏳ Loading...",
    "common.error":             "⚠️ Something went wrong. Please try again.",
    "common.back":              "⬅️ Back",
    "common.cancel":            "❌ Cancel",
    "common.confirm":           "✅ Confirm",
    "common.yes":               "Yes",
    "common.no":                "No",
    "common.or":                "or",
    "common.done":              "✅ Done",
    "common.saved":             "✅ Saved!",
    "common.not_available":     "Not available yet.",

    # ── Welcome / onboarding ──────────────────────────────────────────────
    "welcome.greeting":         "👋 Welcome to Mental Outline VPN, {name}!",
    "welcome.greeting_back":    "👋 Welcome back, {name}!",
    "welcome.choose_lang":      "Please choose your language / ဘာသာစကားရွေးချယ်ပါ:",
    "welcome.lang_saved":       "✅ Language set to English.",
    "welcome.setup_complete":   "✅ All set! You can now use the bot.",

    # ── Language selection ────────────────────────────────────────────────
    "language.select_prompt":   "🌐 Choose your language:",
    "language.english":         "🇬🇧 English",
    "language.myanmar":         "🇲🇲 မြန်မာ",
    "language.changed":         "✅ Language changed to English.",
    "language.already_set":     "ℹ️ English is already your language.",

    # ── Auth / access ─────────────────────────────────────────────────────
    "auth.banned":              "🚫 Your account has been banned. Contact support.",
    "auth.suspended":           "⏸ Your account is temporarily suspended. Contact support.",
    "auth.inactive":            "Your account is inactive.",

    # ── Maintenance ───────────────────────────────────────────────────────
    "maintenance.message":      "🔧 The bot is currently under maintenance. Please try again later.",

    # ── Main menu ─────────────────────────────────────────────────────────
    "menu.packages":            "📦 Packages",
    "menu.my_keys":             "🔑 My VPN Keys",
    "menu.wallet":              "💰 Wallet",
    "menu.language":            "🌐 Language",
    "menu.help":                "ℹ️ Help",
    "menu.profile":             "👤 My Profile",
    "menu.admin":               "🛠 Admin Panel",
    "menu.settings":            "⚙️ Settings",

    # ── Profile ───────────────────────────────────────────────────────────
    "profile.title":            "👤 Your Profile",
    "profile.id":               "🆔 ID: {telegram_id}",
    "profile.name":             "👤 Name: {name}",
    "profile.username":         "🔗 Username: @{username}",
    "profile.role":             "🎭 Role: {role}",
    "profile.status":           "📊 Status: {status}",
    "profile.language":         "🌐 Language: {language}",
    "profile.member_since":     "📅 Member since: {date}",

    # ── Roles ─────────────────────────────────────────────────────────────
    "role.admin":               "Administrator",
    "role.customer":            "Customer",
    "role.reseller":            "Reseller",
    "role.affiliate":           "Affiliate",
    "role.moderator":           "Moderator",
    "role.vip":                 "VIP",

    # ── Statuses ──────────────────────────────────────────────────────────
    "status.active":            "✅ Active",
    "status.inactive":          "💤 Inactive",
    "status.suspended":         "⏸ Suspended",
    "status.banned":            "🚫 Banned",
    "status.pending":           "⏳ Pending",

    # ── Errors ────────────────────────────────────────────────────────────
    "error.unauthorized":       "⛔ You do not have permission to do that.",
    "error.admin_only":         "⛔ This command is for admins only.",
    "error.not_found":          "🔍 Not found.",
    "error.generic":            "⚠️ An unexpected error occurred. Our team has been notified.",
    "error.language_required":  "⚠️ Please select your language first.",

    # ── Placeholders (Phase 1+) ───────────────────────────────────────────
    "placeholder.coming_soon":  "🚧 Coming soon! Stay tuned.",
}
