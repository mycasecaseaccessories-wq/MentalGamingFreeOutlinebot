"""
Myanmar / Burmese (my) translations for the Mental Outline VPN Platform.

This package supersedes locales/my.py (kept for reference).
Keys must match those in locales/en/__init__.py exactly.
Missing keys fall back to English automatically via the Translator.

Phase 0.4: Added auth, language-selection, status, and role keys.
NOTE: Native-speaker review of Phase 0.4 additions is pending.
"""

TRANSLATIONS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────────────────
    "common.loading":           "⏳ ခဏစောင့်ပါ...",
    "common.error":             "⚠️ တစ်ခုခု မှားယွင်းသွားသည်။ ထပ်မံကြိုးစားပါ။",
    "common.back":              "⬅️ နောက်သို့",
    "common.cancel":            "❌ ပယ်ဖျက်ရန်",
    "common.confirm":           "✅ အတည်ပြုရန်",
    "common.yes":               "ဟုတ်သည်",
    "common.no":                "မဟုတ်ပါ",
    "common.or":                "သို့မဟုတ်",
    "common.done":              "✅ ပြီးပါပြီ",
    "common.saved":             "✅ သိမ်းဆည်းပြီး!",
    "common.not_available":     "မရရှိနိုင်သေးပါ။",

    # ── Welcome / onboarding ──────────────────────────────────────────────
    "welcome.greeting":         "👋 Mental Outline VPN မှ ကြိုဆိုပါသည်, {name}!",
    "welcome.greeting_back":    "👋 ပြန်လည်ကြိုဆိုပါသည်, {name}!",
    "welcome.choose_lang":      "ဘာသာစကားရွေးချယ်ပါ / Please choose your language:",
    "welcome.lang_saved":       "✅ မြန်မာဘာသာ သတ်မှတ်ပြီးပါပြီ။",
    "welcome.setup_complete":   "✅ အဆင်သင့်ဖြစ်ပါပြီ! bot ကိုအသုံးပြုနိုင်ပါပြီ။",

    # ── Language selection ────────────────────────────────────────────────
    "language.select_prompt":   "🌐 ဘာသာစကားရွေးချယ်ပါ:",
    "language.english":         "🇬🇧 English",
    "language.myanmar":         "🇲🇲 မြန်မာ",
    "language.changed":         "✅ မြန်မာဘာသာသို့ ပြောင်းလဲပြီးပါပြီ။",
    "language.already_set":     "ℹ️ မြန်မာဘာသာ သတ်မှတ်ပြီးဖြစ်သည်။",

    # ── Auth / access ─────────────────────────────────────────────────────
    "auth.banned":              "🚫 သင့်အကောင့်ကို ပိတ်ထားသည်။ support ကိုဆက်သွယ်ပါ။",
    "auth.suspended":           "⏸ သင့်အကောင့်ကို ယာယီရပ်ဆိုင်းထားသည်။ support ကိုဆက်သွယ်ပါ။",
    "auth.inactive":            "သင့်အကောင့် ပျက်ကွက်နေသည်။",

    # ── Maintenance ───────────────────────────────────────────────────────
    "maintenance.message":      "🔧 Bot ကို ယခုပြင်ဆင်နေသည်။ နောက်မှပြန်လာပါ။",

    # ── Main menu ─────────────────────────────────────────────────────────
    "menu.packages":            "📦 ပက်ကေ့ဂျ်များ",
    "menu.my_keys":             "🔑 ကျွန်ုပ်၏ VPN သော့များ",
    "menu.wallet":              "💰 ပိုက်ဆံအိတ်",
    "menu.language":            "🌐 ဘာသာစကား",
    "menu.help":                "ℹ️ အကူအညီ",
    "menu.profile":             "👤 ကျွန်ုပ်၏ ပရိုဖိုင်",
    "menu.admin":               "🛠 Admin Panel",
    "menu.settings":            "⚙️ ဆက်တင်များ",

    # ── Profile ───────────────────────────────────────────────────────────
    "profile.title":            "👤 ကျွန်ုပ်၏ ပရိုဖိုင်",
    "profile.id":               "🆔 ID: {telegram_id}",
    "profile.name":             "👤 နာမည်: {name}",
    "profile.username":         "🔗 Username: @{username}",
    "profile.role":             "🎭 အဆင့်: {role}",
    "profile.status":           "📊 အခြေအနေ: {status}",
    "profile.language":         "🌐 ဘာသာစကား: {language}",
    "profile.member_since":     "📅 စတင်ထည့်သွင်းသည့်ရက်: {date}",

    # ── Roles ─────────────────────────────────────────────────────────────
    "role.admin":               "စီမံခန့်ခွဲသူ",
    "role.customer":            "ဖောက်သည်",
    "role.reseller":            "ပြန်လည်ရောင်းချသူ",
    "role.affiliate":           "မိတ်ဖက်",
    "role.moderator":           "ကြီးကြပ်သူ",
    "role.vip":                 "VIP",

    # ── Statuses ──────────────────────────────────────────────────────────
    "status.active":            "✅ တက်ကြွသော",
    "status.inactive":          "💤 တက်ကြွမှုမရှိ",
    "status.suspended":         "⏸ ယာယီရပ်ဆိုင်း",
    "status.banned":            "🚫 တားမြစ်",
    "status.pending":           "⏳ စောင့်ဆိုင်းနေ",

    # ── Errors ────────────────────────────────────────────────────────────
    "error.unauthorized":       "⛔ ဤလုပ်ဆောင်ချက်ကို ခွင့်မပြုပါ။",
    "error.admin_only":         "⛔ ဤ command သည် admin များအတွက်သာဖြစ်သည်။",
    "error.not_found":          "🔍 မတွေ့ပါ။",
    "error.generic":            "⚠️ မမျှော်လင့်သောပြဿနာဖြစ်ပွားသည်။ ကျွန်ုပ်တို့ကိုအကြောင်းကြားထားပါသည်။",
    "error.language_required":  "⚠️ ဘာသာစကားကိုအရင်ရွေးချယ်ပါ။",

    # ── Placeholders (Phase 1+) ───────────────────────────────────────────
    "placeholder.coming_soon":  "🚧 မကြာမီလာမည်! ဆက်လက်စောင့်ကြည့်ပါ။",
}
