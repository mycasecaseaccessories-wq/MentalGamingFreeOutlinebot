"""
Feature Flag definitions.

Each flag controls a platform feature that can be toggled at runtime
via the settings table — no code deployment required.

Usage (Phase 2+):
    from app.services import SettingsService

    svc = SettingsService(db)
    if await svc.get(FeatureFlags.ENABLE_WALLET, default=False):
        # wallet flows are active
        ...

Adding a new flag:
    1. Add a constant here (PREFIX_FEATURE_*).
    2. Register it in FEATURE_FLAG_DEFAULTS with its default value and description.
    3. The SettingsService.seed_defaults() call will persist it on first startup.

This module intentionally has NO async code and NO database imports.
It is a pure constant registry — safe to import anywhere.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Flag key constants  (stored as setting keys in the database)
# ---------------------------------------------------------------------------

class FeatureFlags:
    """
    Namespace for all feature-flag setting keys.

    Every constant maps 1-to-1 to a row in the settings table.
    """

    # ── Commerce ──────────────────────────────────────────────────────────────
    ENABLE_WALLET: str   = "feature_enable_wallet"
    """Allow users to top up and spend wallet balance."""

    ENABLE_PURCHASE: str = "feature_enable_purchase"
    """Allow users to purchase VPN packages."""

    # ── Onboarding ────────────────────────────────────────────────────────────
    ENABLE_FREE_TRIAL: str = "feature_enable_free_trial"
    """Grant a free trial key to new users on first /start."""

    ENABLE_REFERRAL: str   = "feature_enable_referral"
    """Activate the referral / affiliate programme."""

    # ── Distribution ──────────────────────────────────────────────────────────
    ENABLE_FORCE_JOIN: str = "feature_enable_force_join"
    """
    Require users to join a Telegram channel/group before using the bot.
    Configure the channel username via the 'force_join_channel' setting.
    """

    # ── Operations ────────────────────────────────────────────────────────────
    ENABLE_MAINTENANCE: str = "feature_enable_maintenance"
    """
    Put the bot into maintenance mode.
    Non-admin users receive a maintenance message; all other actions are blocked.
    """

    ENABLE_BROADCAST: str = "feature_enable_broadcast"
    """Allow admins to send broadcast messages to all users."""

    ENABLE_NOTIFICATIONS: str = "feature_enable_notifications"
    """Enable automated notifications (expiry reminders, system alerts, etc.)."""

    # ── Insights ──────────────────────────────────────────────────────────────
    ENABLE_ANALYTICS: str = "feature_enable_analytics"
    """Collect and expose platform usage analytics for the admin panel."""


# ---------------------------------------------------------------------------
# Default values for every feature flag
# ---------------------------------------------------------------------------
# Structure: key → { "value": bool, "description": str, "is_public": bool }

FEATURE_FLAG_DEFAULTS: dict[str, dict] = {
    FeatureFlags.ENABLE_WALLET: {
        "value": False,
        "description": "Allow users to top up and spend wallet balance.",
        "is_public": False,
    },
    FeatureFlags.ENABLE_PURCHASE: {
        "value": False,
        "description": "Allow users to purchase VPN packages.",
        "is_public": False,
    },
    FeatureFlags.ENABLE_FREE_TRIAL: {
        "value": True,
        "description": "Grant a free trial key to new users on first /start.",
        "is_public": False,
    },
    FeatureFlags.ENABLE_REFERRAL: {
        "value": False,
        "description": "Activate the referral / affiliate programme.",
        "is_public": False,
    },
    FeatureFlags.ENABLE_FORCE_JOIN: {
        "value": False,
        "description": "Require users to join a channel before using the bot.",
        "is_public": False,
    },
    FeatureFlags.ENABLE_MAINTENANCE: {
        "value": False,
        "description": "Put the bot into maintenance mode for non-admin users.",
        "is_public": True,
    },
    FeatureFlags.ENABLE_BROADCAST: {
        "value": True,
        "description": "Allow admins to send broadcast messages to all users.",
        "is_public": False,
    },
    FeatureFlags.ENABLE_NOTIFICATIONS: {
        "value": True,
        "description": "Enable automated notifications (expiry reminders, etc.).",
        "is_public": False,
    },
    FeatureFlags.ENABLE_ANALYTICS: {
        "value": False,
        "description": "Collect and expose platform usage analytics.",
        "is_public": False,
    },
}
