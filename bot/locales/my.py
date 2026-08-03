"""
Myanmar (Burmese) translations.

Keys must match those defined in locales/en.py exactly.
Missing keys fall back to English automatically via the Translator.

NOTE: Myanmar translations are placeholder stubs in Phase 0.
      Native-speaker review and full translation is scheduled for Phase 1.
"""

TRANSLATIONS: dict[str, str] = {
    # ── Common ────────────────────────────────────────────────────────────
    "common.loading":       "⏳ ခဏစောင့်ပါ...",
    "common.error":         "⚠️ တစ်ခုခု မှားယွင်းသွားသည်။ ထပ်မံကြိုးစားပါ။",
    "common.back":          "⬅️ နောက်သို့",
    "common.cancel":        "❌ ပယ်ဖျက်ရန်",
    "common.confirm":       "✅ အတည်ပြုရန်",
    "common.yes":           "ဟုတ်သည်",
    "common.no":            "မဟုတ်ပါ",

    # ── Welcome / onboarding ──────────────────────────────────────────────
    "welcome.greeting":     "👋 Mental Outline VPN မှ ကြိုဆိုပါသည်, {name}!",
    "welcome.choose_lang":  "ကျေးဇူးပြု၍ သင့်ဘာသာစကားကို ရွေးချယ်ပါ:",

    # ── Main menu ─────────────────────────────────────────────────────────
    "menu.packages":        "📦 ပက်ကေ့ဂျ်များ",
    "menu.my_keys":         "🔑 ကျွန်ုပ်၏ VPN သော့များ",
    "menu.wallet":          "💰 ပိုက်ဆံအိတ်",
    "menu.language":        "🌐 ဘာသာစကား",
    "menu.help":            "ℹ️ အကူအညီ",
    "menu.admin":           "🛠 စီမံခန့်ခွဲသူ panel",

    # ── Errors ────────────────────────────────────────────────────────────
    "error.unauthorized":   "⛔ သင့်တွင် ခွင့်ပြုချက် မရှိပါ။",
    "error.not_found":      "🔍 ရှာမတွေ့ပါ။",
    "error.generic":        "⚠️ မမျှော်လင့်သော အမှားတစ်ခု ဖြစ်ပေါ်သည်။ ကျွန်ုပ်တို့ အသိပေးပြီးပြီ။",

    # ── Placeholders ─────────────────────────────────────────────────────
    "placeholder.coming_soon": "🚧 မကြာမီ ရရှိမည်ဖြစ်သည်!",
}
