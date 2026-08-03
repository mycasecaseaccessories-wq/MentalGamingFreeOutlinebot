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
