"""
Default platform settings.

This module defines every setting that must exist in the database from the
first startup.  SettingsService.seed_defaults() inserts these rows (with
their default values) on boot if they are not already present — existing
values are never overwritten.

Structure of each entry:
    key          Unique setting key stored in the DB (snake_case).
    value        Default value (Python native — will be coerced to str).
    type         One of: str | int | float | bool | json | list.
    category     Category slug from SettingCategory.
    description  Human-readable label shown in the admin panel.
    is_public    Whether non-admin code may read this setting.

Adding a new setting:
    1. Add a constant to SettingKeys (optional but recommended).
    2. Append an entry to DEFAULT_SETTINGS.
    3. SettingsService.seed_defaults() will persist it on next startup.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Category constants
# ---------------------------------------------------------------------------

class SettingCategory:
    """Canonical category slugs for grouping settings in the admin panel."""

    GENERAL: str       = "general"
    LANGUAGE: str      = "language"
    WALLET: str        = "wallet"
    VPN: str           = "vpn"
    PACKAGES: str      = "packages"
    SERVERS: str       = "servers"
    GROWTH: str        = "growth"
    NOTIFICATIONS: str = "notifications"
    SECURITY: str      = "security"
    MAINTENANCE: str   = "maintenance"
    ANALYTICS: str     = "analytics"


# ---------------------------------------------------------------------------
# Setting key constants  (optional — prevents typos in call sites)
# ---------------------------------------------------------------------------

class SettingKeys:
    """Namespace for all non-feature-flag setting keys."""

    # General
    BOT_NAME: str            = "bot_name"
    SUPPORT_USERNAME: str    = "support_username"
    DEFAULT_LANGUAGE: str    = "default_language"
    TIMEZONE: str            = "timezone"
    CURRENCY: str            = "currency"
    MANUAL_PAYMENT_METHODS: str = "manual_payment_methods"

    # VPN
    MAX_DEVICES: str         = "vpn_max_devices"
    SERVER_SELECTION: str    = "vpn_server_selection_mode"
    AUTO_SYNC_INTERVAL: str  = "vpn_auto_sync_interval_seconds"

    # Maintenance
    MAINTENANCE_MESSAGE: str = "maintenance_message"
    FORCE_JOIN_CHANNEL: str  = "force_join_channel"

    # Growth
    REFERRAL_COMMISSION_PCT: str = "growth_referral_commission_pct"
    FREE_TRIAL_DURATION_DAYS: str = "growth_free_trial_duration_days"
    FREE_TRIAL_ENABLED: str = "free_trial_enabled"
    FREE_TRIAL_DATA_PER_CLAIM_BYTES: str = "free_trial_data_per_claim_bytes"
    FREE_TRIAL_DURATION_SECONDS: str = "free_trial_duration_seconds"
    FREE_TRIAL_DEVICE_LIMIT: str = "free_trial_device_limit"
    FREE_TRIAL_NORMAL_CLAIMS_PER_PERIOD: str = "free_trial_normal_claims_per_period"
    FREE_TRIAL_DAILY_DATA_CAP_BYTES: str = "free_trial_daily_data_cap_bytes"
    FREE_TRIAL_RESET_TIMEZONE: str = "free_trial_reset_timezone"
    FREE_TRIAL_EXTRA_CLAIMS_ENABLED: str = "free_trial_extra_claims_enabled"
    FREE_TRIAL_PAID_UPGRADE_ENABLED: str = "free_trial_paid_upgrade_enabled"
    FREE_TRIAL_SERVER_SELECTION_MODE: str = "free_trial_server_selection_mode"
    REFERRAL_ABUSE_RATE_LIMIT_SECONDS: str = "free_trial_abuse_rate_limit_seconds"
    FREE_TRIAL_ABUSE_RATE_LIMIT_SECONDS: str = "free_trial_abuse_rate_limit_seconds"
    REFERRAL_ENABLED: str = "referral_enabled"
    REFERRAL_REQUIRE_NEW_USER: str = "referral_require_new_user"
    REFERRAL_FIRST_ATTRIBUTION_WINS: str = "referral_first_attribution_wins"
    REFERRAL_START_PREFIX: str = "referral_start_prefix"
    REFERRAL_MIN_FIRST_SEEN_AGE_SECONDS: str = "referral_min_first_seen_age_seconds"
    REFERRAL_QUALIFICATION_WAIT_SECONDS: str = "referral_qualification_wait_seconds"
    REFERRAL_REQUIRE_FORCE_JOIN: str = "referral_require_force_join"
    REFERRAL_REQUIRE_FREE_TRIAL_ACTIVATION: str = "referral_require_free_trial_activation"
    REFERRAL_REQUIRE_PAID_PURCHASE: str = "referral_require_paid_purchase"
    REFERRAL_BURST_DETECTION_ENABLED: str = "referral_burst_detection_enabled"
    REFERRAL_BURST_THRESHOLD: str = "referral_burst_threshold"
    REFERRAL_BURST_WINDOW_SECONDS: str = "referral_burst_window_seconds"
    REFERRAL_REVIEW_SUSPICIOUS: str = "referral_review_suspicious"
    REFERRAL_REWARDS_ENABLED: str = "referral_rewards_enabled"
    REFERRAL_REWARD_MODE: str = "referral_reward_mode"
    REFERRAL_REQUIRED_QUALIFIED_COUNT: str = "referral_required_qualified_count"
    REFERRAL_REFERRER_REWARD_TYPE: str = "referral_referrer_reward_type"
    REFERRAL_REFERRER_REWARD_VALUE: str = "referral_referrer_reward_value"
    REFERRAL_REFERRED_REWARD_TYPE: str = "referral_referred_reward_type"
    REFERRAL_REFERRED_REWARD_VALUE: str = "referral_referred_reward_value"
    REFERRAL_REWARD_DAILY_LIMIT: str = "referral_reward_daily_limit"
    REFERRAL_REWARD_WEEKLY_LIMIT: str = "referral_reward_weekly_limit"
    REFERRAL_REWARD_MONTHLY_LIMIT: str = "referral_reward_monthly_limit"
    REFERRAL_REWARD_LIFETIME_LIMIT: str = "referral_reward_lifetime_limit"
    REFERRAL_REWARD_COOLDOWN_SECONDS: str = "referral_reward_cooldown_seconds"
    REFERRAL_REWARD_EXPIRY_SECONDS: str = "referral_reward_expiry_seconds"
    REFERRAL_REWARD_WALLET_CURRENCY: str = "referral_reward_wallet_currency"

    # Notifications
    EXPIRY_REMINDER_DAYS: str = "notifications_expiry_reminder_days"

    # Security
    MAX_FAILED_LOGINS: str   = "security_max_failed_logins"
    SESSION_TTL_HOURS: str   = "security_session_ttl_hours"

    # Analytics
    STATS_RETENTION_DAYS: str = "analytics_stats_retention_days"


# ---------------------------------------------------------------------------
# Default settings registry
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: list[dict] = [

    # ── General ───────────────────────────────────────────────────────────────
    {
        "key": SettingKeys.BOT_NAME,
        "value": "Mental VPN",
        "type": "str",
        "category": SettingCategory.GENERAL,
        "description": "Display name of the bot shown in messages and menus.",
        "is_public": True,
    },
    {
        "key": SettingKeys.SUPPORT_USERNAME,
        "value": "",
        "type": "str",
        "category": SettingCategory.GENERAL,
        "description": "Telegram @username of the support contact (without '@').",
        "is_public": True,
    },
    {
        "key": SettingKeys.DEFAULT_LANGUAGE,
        "value": "en",
        "type": "str",
        "category": SettingCategory.GENERAL,
        "description": "Default UI language for new users: 'en' or 'my'.",
        "is_public": True,
    },
    {
        "key": SettingKeys.TIMEZONE,
        "value": "Asia/Yangon",
        "type": "str",
        "category": SettingCategory.GENERAL,
        "description": "IANA timezone for display and scheduler (e.g. 'Asia/Yangon').",
        "is_public": False,
    },
    {
        "key": SettingKeys.CURRENCY,
        "value": "MMK",
        "type": "str",
        "category": SettingCategory.GENERAL,
        "description": "Default currency code for price display (e.g. 'MMK', 'USD').",
        "is_public": True,
    },
    {
        "key": SettingKeys.MANUAL_PAYMENT_METHODS,
        "value": [],
        "type": "list",
        "category": SettingCategory.WALLET,
        "description": "Customer-facing manual payment destinations; never store secrets here.",
        "is_public": True,
    },

    # ── VPN ───────────────────────────────────────────────────────────────────
    {
        "key": SettingKeys.MAX_DEVICES,
        "value": 3,
        "type": "int",
        "category": SettingCategory.VPN,
        "description": "Maximum number of devices (active VPN keys) per user.",
        "is_public": True,
    },
    {
        "key": SettingKeys.SERVER_SELECTION,
        "value": "auto",
        "type": "str",
        "category": SettingCategory.VPN,
        "description": "Server selection mode: 'auto' (least-loaded) or 'manual'.",
        "is_public": False,
    },
    {
        "key": SettingKeys.AUTO_SYNC_INTERVAL,
        "value": 300,
        "type": "int",
        "category": SettingCategory.VPN,
        "description": "Interval in seconds between automatic key-sync cycles.",
        "is_public": False,
    },

    # ── Maintenance ───────────────────────────────────────────────────────────
    {
        "key": SettingKeys.MAINTENANCE_MESSAGE,
        "value": "The bot is currently under maintenance. Please try again later.",
        "type": "str",
        "category": SettingCategory.MAINTENANCE,
        "description": "Message shown to users during maintenance mode.",
        "is_public": True,
    },
    {
        "key": SettingKeys.FORCE_JOIN_CHANNEL,
        "value": "",
        "type": "str",
        "category": SettingCategory.MAINTENANCE,
        "description": "Channel username users must join (e.g. 'my_channel'). "
                       "Leave empty to disable force-join.",
        "is_public": False,
    },

    # ── Growth ────────────────────────────────────────────────────────────────
    {
        "key": SettingKeys.REFERRAL_COMMISSION_PCT,
        "value": 10.0,
        "type": "float",
        "category": SettingCategory.GROWTH,
        "description": "Referral commission as a percentage of referred user's payments.",
        "is_public": False,
    },
    {
        "key": SettingKeys.FREE_TRIAL_DURATION_DAYS,
        "value": 3,
        "type": "int",
        "category": SettingCategory.GROWTH,
        "description": "Duration of the free trial in days.",
        "is_public": True,
    },

    # ── Free Trial ────────────────────────────────────────────────────────────
    {"key": SettingKeys.FREE_TRIAL_ENABLED, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Allow new Free Trial claims.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_DATA_PER_CLAIM_BYTES, "value": 536870912, "type": "int", "category": SettingCategory.GROWTH, "description": "Canonical Free Trial data allowance per claim in bytes.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_DURATION_SECONDS, "value": 86400, "type": "int", "category": SettingCategory.GROWTH, "description": "Free Trial duration per claim in seconds.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_DEVICE_LIMIT, "value": 1, "type": "int", "category": SettingCategory.GROWTH, "description": "Free Trial device policy limit.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_NORMAL_CLAIMS_PER_PERIOD, "value": 1, "type": "int", "category": SettingCategory.GROWTH, "description": "Normal Free Trial claims allowed per reset period.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_DAILY_DATA_CAP_BYTES, "value": 0, "type": "int", "category": SettingCategory.GROWTH, "description": "Optional total Free Trial data cap per reset period in bytes; zero disables it.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_RESET_TIMEZONE, "value": "Asia/Yangon", "type": "str", "category": SettingCategory.GROWTH, "description": "Timezone used for Free Trial claim periods.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_EXTRA_CLAIMS_ENABLED, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Allow active extra Free Trial entitlements.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_PAID_UPGRADE_ENABLED, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Allow paid upgrades and conversion from active Free Trial keys.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_SERVER_SELECTION_MODE, "value": "auto", "type": "str", "category": SettingCategory.GROWTH, "description": "Free Trial server selection mode.", "is_public": False},
    {"key": SettingKeys.FREE_TRIAL_ABUSE_RATE_LIMIT_SECONDS, "value": 3, "type": "int", "category": SettingCategory.SECURITY, "description": "Minimum interval between repeated Free Trial actions.", "is_public": False},
    {"key": SettingKeys.REFERRAL_ENABLED, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Enable new referral attribution.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REQUIRE_NEW_USER, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Allow referral attribution only for newly registered users.", "is_public": False},
    {"key": SettingKeys.REFERRAL_FIRST_ATTRIBUTION_WINS, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Preserve the first valid primary referrer.", "is_public": False},
    {"key": SettingKeys.REFERRAL_START_PREFIX, "value": "ref_", "type": "str", "category": SettingCategory.GROWTH, "description": "Telegram referral /start payload namespace.", "is_public": True},
    {"key": SettingKeys.REFERRAL_MIN_FIRST_SEEN_AGE_SECONDS, "value": 259200, "type": "int", "category": SettingCategory.SECURITY, "description": "Minimum server-observed age of a referred user; not Telegram account age.", "is_public": False},
    {"key": SettingKeys.REFERRAL_QUALIFICATION_WAIT_SECONDS, "value": 86400, "type": "int", "category": SettingCategory.GROWTH, "description": "Wait after first valid attribution before qualification.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REQUIRE_FORCE_JOIN, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Require current Force Join verification for qualification.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REQUIRE_FREE_TRIAL_ACTIVATION, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Require authoritative Free Trial activation for qualification.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REQUIRE_PAID_PURCHASE, "value": False, "type": "bool", "category": SettingCategory.GROWTH, "description": "Require an authoritative successful paid purchase for qualification.", "is_public": False},
    {"key": SettingKeys.REFERRAL_BURST_DETECTION_ENABLED, "value": True, "type": "bool", "category": SettingCategory.SECURITY, "description": "Hold suspicious referral velocity for review.", "is_public": False},
    {"key": SettingKeys.REFERRAL_BURST_THRESHOLD, "value": 10, "type": "int", "category": SettingCategory.SECURITY, "description": "Maximum referral events in the burst window before review.", "is_public": False},
    {"key": SettingKeys.REFERRAL_BURST_WINDOW_SECONDS, "value": 300, "type": "int", "category": SettingCategory.SECURITY, "description": "Referral burst detection window in seconds.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REVIEW_SUSPICIOUS, "value": True, "type": "bool", "category": SettingCategory.SECURITY, "description": "Require admin review instead of automatic rewards for suspicious referrals.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARDS_ENABLED, "value": True, "type": "bool", "category": SettingCategory.GROWTH, "description": "Enable referral reward fulfillment.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_MODE, "value": "every_n", "type": "str", "category": SettingCategory.GROWTH, "description": "Reward mode: every_n qualified referrals or every valid qualification.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REQUIRED_QUALIFIED_COUNT, "value": 3, "type": "int", "category": SettingCategory.GROWTH, "description": "Qualified referrals required to open each reward cycle.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REFERRER_REWARD_TYPE, "value": "extra_trial", "type": "str", "category": SettingCategory.GROWTH, "description": "Reward type for the referrer.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REFERRER_REWARD_VALUE, "value": 1, "type": "int", "category": SettingCategory.GROWTH, "description": "Reward amount for the referrer.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REFERRED_REWARD_TYPE, "value": "extra_trial", "type": "str", "category": SettingCategory.GROWTH, "description": "Reward type for the referred user.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REFERRED_REWARD_VALUE, "value": 1, "type": "int", "category": SettingCategory.GROWTH, "description": "Reward amount for the referred user.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_DAILY_LIMIT, "value": 5, "type": "int", "category": SettingCategory.GROWTH, "description": "Maximum referral rewards per beneficiary per UTC day; zero means unlimited.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_WEEKLY_LIMIT, "value": 20, "type": "int", "category": SettingCategory.GROWTH, "description": "Maximum referral rewards per beneficiary per UTC week; zero means unlimited.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_MONTHLY_LIMIT, "value": 50, "type": "int", "category": SettingCategory.GROWTH, "description": "Maximum referral rewards per beneficiary per UTC month; zero means unlimited.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_LIFETIME_LIMIT, "value": 0, "type": "int", "category": SettingCategory.GROWTH, "description": "Maximum lifetime referral rewards per beneficiary; zero means unlimited.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_COOLDOWN_SECONDS, "value": 3600, "type": "int", "category": SettingCategory.GROWTH, "description": "Minimum time between rewards for one beneficiary.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_EXPIRY_SECONDS, "value": 2592000, "type": "int", "category": SettingCategory.GROWTH, "description": "Expiry for time-limited referral entitlements.", "is_public": False},
    {"key": SettingKeys.REFERRAL_REWARD_WALLET_CURRENCY, "value": "MMK", "type": "str", "category": SettingCategory.WALLET, "description": "Currency used by wallet referral bonuses.", "is_public": False},

    # ── Notifications ─────────────────────────────────────────────────────────
    {
        "key": SettingKeys.EXPIRY_REMINDER_DAYS,
        "value": 3,
        "type": "int",
        "category": SettingCategory.NOTIFICATIONS,
        "description": "Days before expiry when a renewal reminder is sent.",
        "is_public": False,
    },

    # ── Security ──────────────────────────────────────────────────────────────
    {
        "key": SettingKeys.MAX_FAILED_LOGINS,
        "value": 5,
        "type": "int",
        "category": SettingCategory.SECURITY,
        "description": "Maximum consecutive failed admin actions before rate-limiting.",
        "is_public": False,
    },
    {
        "key": SettingKeys.SESSION_TTL_HOURS,
        "value": 24,
        "type": "int",
        "category": SettingCategory.SECURITY,
        "description": "Session / token TTL in hours.",
        "is_public": False,
    },

    # ── Analytics ─────────────────────────────────────────────────────────────
    {
        "key": SettingKeys.STATS_RETENTION_DAYS,
        "value": 90,
        "type": "int",
        "category": SettingCategory.ANALYTICS,
        "description": "Number of days to retain aggregated analytics records.",
        "is_public": False,
    },
]
