"""
UserPreference domain model.

Plain Python dataclass representing a user's configurable preferences.
Not coupled to SQLAlchemy — returned by PreferenceService and consumed
by handlers, middleware, and mini-app integration layers.

Phase 0.5: Initial schema matching UserPreferenceORM.

Adding a new preference:
  1. Add the field here with a matching default.
  2. Add a PreferenceKey constant below.
  3. Add the column to UserPreferenceORM (database/models/user_preference.py).
  4. Write an Alembic migration.
  5. Update PreferenceService.DEFAULTS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Preference key constants  (prevents typos at call sites)
# ---------------------------------------------------------------------------

class PreferenceKey:
    """
    String constants for every preference field name.

    Always use these constants instead of bare string literals so that
    IDEs catch typos and renames propagate automatically.

    Usage:
        from app.models.user_preference import PreferenceKey
        value = await svc.get_preference(user_id, PreferenceKey.LANGUAGE)
    """

    # Language & region
    LANGUAGE:                  str = "language"
    TIMEZONE:                  str = "timezone"
    PREFERRED_CURRENCY:        str = "preferred_currency"

    # Notifications
    NOTIFICATION_ENABLED:      str = "notification_enabled"
    BROADCAST_ENABLED:         str = "broadcast_enabled"

    # Privacy
    PRIVACY_MODE:              str = "privacy_mode"

    # UI / theme
    THEME:                     str = "theme"
    LAST_MENU:                 str = "last_menu"
    LANGUAGE_SELECTED:         str = "language_selected"

    # Server preference
    PREFERRED_SERVER_COUNTRY:  str = "preferred_server_country"

    # Utility: all known keys as a frozenset for validation
    ALL: frozenset[str] = frozenset({
        LANGUAGE,
        TIMEZONE,
        PREFERRED_CURRENCY,
        NOTIFICATION_ENABLED,
        BROADCAST_ENABLED,
        PRIVACY_MODE,
        THEME,
        LAST_MENU,
        LANGUAGE_SELECTED,
        PREFERRED_SERVER_COUNTRY,
    })

    @classmethod
    def is_valid(cls, key: str) -> bool:
        """Return True when *key* is a recognised preference key."""
        return key in cls.ALL


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass
class UserPreference:
    """
    Represents all configurable preferences for a single user.

    Attributes:
        user_id                   Telegram user ID (mirrors users.telegram_id).
        language                  Preferred UI language code ('en' | 'my').
        timezone                  IANA timezone string (e.g. 'Asia/Rangoon').
        preferred_currency        ISO 4217 currency code ('MMK', 'USD', …).
        notification_enabled      Receive expiry / system notifications.
        broadcast_enabled         Receive admin broadcasts.
        privacy_mode              Minimise data logging (Phase 3+).
        theme                     Mini App UI theme ('default' | 'dark' | …).
        last_menu                 Last visited menu identifier for state restore.
        preferred_server_country  ISO 3166-1 alpha-2 country code, or None.
        created_at                UTC timestamp of preference row creation.
        updated_at                UTC timestamp of last preference update.
    """

    user_id: int

    # Language & region
    language:                 str  = "en"
    timezone:                 str  = "Asia/Rangoon"
    preferred_currency:       str  = "MMK"

    # Notifications
    notification_enabled:     bool = True
    broadcast_enabled:        bool = True

    # Privacy
    privacy_mode:             bool = False

    # UI / theme
    theme:                    str  = "default"
    last_menu:                Optional[str] = None
    language_selected:       bool = False

    # Server preference
    preferred_server_country: Optional[str] = None

    # Audit
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ── Helpers ───────────────────────────────────────────────────────────

    def get(self, key: str) -> Any:
        """
        Return the value of a preference by key name.

        Args:
            key: A PreferenceKey constant string.

        Returns:
            The preference value.

        Raises:
            AttributeError: If *key* is not a valid preference attribute.
        """
        if not hasattr(self, key):
            raise AttributeError(
                f"{self.__class__.__name__!r} has no preference {key!r}. "
                f"Valid keys: {sorted(PreferenceKey.ALL)}"
            )
        return getattr(self, key)

    def to_dict(self) -> dict[str, Any]:
        """
        Return all preferences as a plain dict (key → value).

        Timestamps are excluded — this is a preferences snapshot, not a
        full serialisation.

        Returns:
            Dict mapping every PreferenceKey to its current value.
        """
        return {key: self.get(key) for key in PreferenceKey.ALL}

    def __repr__(self) -> str:
        return (
            f"UserPreference("
            f"user_id={self.user_id}, "
            f"language={self.language!r}, "
            f"theme={self.theme!r}, "
            f"notifications={self.notification_enabled})"
        )
