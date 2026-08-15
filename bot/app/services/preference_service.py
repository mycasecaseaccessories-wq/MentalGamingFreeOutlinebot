"""
PreferenceService — per-user preference management.

Responsibilities:
  • Get-or-create a user's preference row (lazy initialisation).
  • Read a single preference value or all preferences at once.
  • Set one or many preferences atomically.
  • Reset one preference or all preferences to their defaults.

Design notes:
  • All preferences have defaults so calling get_preference() never
    returns None for a recognised key.
  • In-memory cache (per service instance) avoids a DB hit on every
    translated message; cache is invalidated on every set/reset call.
  • The service never exposes ORM objects — it returns UserPreference
    domain objects (app/models/user_preference.py).

Phase 0.5: Full implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.models.user_preference import PreferenceKey, UserPreference
from database.connection import DatabaseManager
from database.models.user_preference import UserPreferenceORM
from database.repositories.preference_repository import PreferenceRepository

from .base import BaseService

logger = logging.getLogger(__name__)


def _orm_to_domain(row: UserPreferenceORM) -> UserPreference:
    """Map a UserPreferenceORM row to a UserPreference domain object."""
    return UserPreference(
        user_id=row.user_id,
        language=row.language,
        timezone=row.timezone,
        preferred_currency=row.preferred_currency,
        notification_enabled=row.notification_enabled,
        broadcast_enabled=row.broadcast_enabled,
        privacy_mode=row.privacy_mode,
        theme=row.theme,
        last_menu=row.last_menu,
        preferred_server_country=row.preferred_server_country,
        language_selected=getattr(row, "language_selected", False),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PreferenceService(BaseService):
    """
    Manages per-user configurable preferences.

    Each supported preference has a canonical default declared in DEFAULTS.
    Any key not in DEFAULTS is rejected at service level to prevent
    accidental persistence of arbitrary data.
    """

    # Default values for every supported preference key.
    # Update this dict whenever a new PreferenceKey constant is added.
    DEFAULTS: dict[str, Any] = {
        PreferenceKey.LANGUAGE:                 "en",
        PreferenceKey.TIMEZONE:                 "Asia/Rangoon",
        PreferenceKey.PREFERRED_CURRENCY:       "MMK",
        PreferenceKey.NOTIFICATION_ENABLED:     True,
        PreferenceKey.BROADCAST_ENABLED:        True,
        PreferenceKey.PRIVACY_MODE:             False,
        PreferenceKey.THEME:                    "default",
        PreferenceKey.LAST_MENU:                None,
        PreferenceKey.LANGUAGE_SELECTED:       False,
        PreferenceKey.PREFERRED_SERVER_COUNTRY: None,
    }

    # Valid theme values accepted by set_preference().
    VALID_THEMES = frozenset({"default", "dark", "light", "system"})

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        super().__init__(db)
        # Per-instance in-memory cache: user_id → UserPreference.
        # Invalidated on every write so stale values are never returned.
        self._cache: dict[int, UserPreference] = {}

    # ── Internal helpers ──────────────────────────────────────────────────

    def _validate_key(self, key: str) -> None:
        """Raise ValueError when *key* is not a recognised preference key."""
        if not PreferenceKey.is_valid(key):
            raise ValueError(
                f"Unknown preference key {key!r}. "
                f"Valid keys: {sorted(PreferenceKey.ALL)}"
            )

    def _validate_value(self, key: str, value: Any) -> Any:
        """
        Coerce and validate *value* for *key*.

        Returns the (possibly coerced) value.

        Raises:
            ValueError: When the value is outside the accepted range.
        """
        if key == PreferenceKey.LANGUAGE:
            supported = {"en", "my"}
            if value not in supported:
                raise ValueError(
                    f"Unsupported language {value!r}. Supported: {sorted(supported)}"
                )
        elif key == PreferenceKey.THEME:
            if value not in self.VALID_THEMES:
                raise ValueError(
                    f"Unsupported theme {value!r}. Valid: {sorted(self.VALID_THEMES)}"
                )
        elif key in (
            PreferenceKey.NOTIFICATION_ENABLED,
            PreferenceKey.BROADCAST_ENABLED,
            PreferenceKey.PRIVACY_MODE,
            PreferenceKey.LANGUAGE_SELECTED,
        ):
            # Accept bool or bool-ish strings/ints.
            if isinstance(value, str):
                value = value.lower() in ("true", "1", "yes", "on")
            else:
                value = bool(value)
        return value

    async def _get_or_create_row(self, user_id: int) -> UserPreference:
        """Fetch or lazily create the preference row for *user_id*."""
        async with self.db.session() as session:
            repo = PreferenceRepository(session)
            row, _ = await repo.upsert(user_id)
        return _orm_to_domain(row)

    # ── Public API ────────────────────────────────────────────────────────

    async def get_preference(self, user_id: int, key: str) -> Any:
        """
        Return the value of a single preference for *user_id*.

        Creates a default preference row if none exists yet.
        Returns the registered default when the row has no value set
        (i.e. for nullable columns that are None).

        Args:
            user_id: Telegram user ID.
            key:     A PreferenceKey constant string.

        Returns:
            The preference value (type depends on the key).

        Raises:
            ValueError: If *key* is not a recognised PreferenceKey.
        """
        self._validate_key(key)

        # Check in-memory cache first.
        if user_id in self._cache:
            return self._cache[user_id].get(key)

        pref = await self._get_or_create_row(user_id)
        self._cache[user_id] = pref
        return pref.get(key)

    async def set_preference(self, user_id: int, key: str, value: Any) -> UserPreference:
        """
        Persist a single preference and return the updated domain object.

        Validates *value* before writing.  Invalidates the in-memory cache
        for this user so the next read fetches the fresh row.

        Args:
            user_id: Telegram user ID.
            key:     A PreferenceKey constant string.
            value:   New preference value.

        Returns:
            Updated UserPreference domain object.

        Raises:
            ValueError: If *key* is invalid or *value* is out of range.
        """
        self._validate_key(key)
        value = self._validate_value(key, value)

        async with self.db.session() as session:
            repo = PreferenceRepository(session)
            row = await repo.set_field(user_id, key, value)

        pref = _orm_to_domain(row)
        self._cache[user_id] = pref
        logger.info(
            "Preference set — user_id=%s key=%s value=%r", user_id, key, value
        )
        return pref

    async def set_preferences(
        self, user_id: int, updates: dict[str, Any]
    ) -> UserPreference:
        """
        Set multiple preferences atomically.

        All keys and values are validated before any write occurs.

        Args:
            user_id:  Telegram user ID.
            updates:  Dict of {PreferenceKey: new_value}.

        Returns:
            Updated UserPreference domain object.

        Raises:
            ValueError: If any key or value is invalid.
        """
        # Validate all entries before touching the DB.
        validated: dict[str, Any] = {}
        for key, value in updates.items():
            self._validate_key(key)
            validated[key] = self._validate_value(key, value)

        async with self.db.session() as session:
            repo = PreferenceRepository(session)
            row = await repo.set_fields(user_id, validated)

        pref = _orm_to_domain(row)
        self._cache[user_id] = pref
        logger.info(
            "Preferences updated — user_id=%s keys=%s",
            user_id, list(validated.keys()),
        )
        return pref

    async def reset_preference(self, user_id: int, key: str) -> UserPreference:
        """
        Reset a single preference to its registered default.

        Args:
            user_id: Telegram user ID.
            key:     A PreferenceKey constant string.

        Returns:
            Updated UserPreference domain object.

        Raises:
            ValueError: If *key* is not a recognised PreferenceKey.
        """
        self._validate_key(key)
        default = self.DEFAULTS[key]

        async with self.db.session() as session:
            repo = PreferenceRepository(session)
            row = await repo.reset_field(user_id, key, default)

        pref = _orm_to_domain(row)
        self._cache[user_id] = pref
        logger.info(
            "Preference reset to default — user_id=%s key=%s default=%r",
            user_id, key, default,
        )
        return pref

    async def reset_all_preferences(self, user_id: int) -> UserPreference:
        """
        Delete the user's preference row and recreate it with all defaults.

        Use this when a user explicitly resets all personalisation settings.

        Args:
            user_id: Telegram user ID.

        Returns:
            Fresh UserPreference domain object with all defaults.
        """
        async with self.db.session() as session:
            repo = PreferenceRepository(session)
            row = await repo.reset(user_id)

        pref = _orm_to_domain(row)
        self._cache[user_id] = pref
        logger.info("All preferences reset — user_id=%s", user_id)
        return pref

    async def get_all_preferences(self, user_id: int) -> UserPreference:
        """
        Return all preferences for *user_id* as a single domain object.

        Creates a default preference row if none exists yet.
        Results are cached in memory until the next write.

        Args:
            user_id: Telegram user ID.

        Returns:
            UserPreference domain object with all current values.
        """
        if user_id in self._cache:
            return self._cache[user_id]

        pref = await self._get_or_create_row(user_id)
        self._cache[user_id] = pref
        return pref

    async def get_or_create(self, user_id: int) -> tuple[UserPreference, bool]:
        """
        Return the preference row or create a default one.

        Args:
            user_id: Telegram user ID.

        Returns:
            Tuple of (UserPreference, created: bool).
        """
        if user_id in self._cache:
            return self._cache[user_id], False

        async with self.db.session() as session:
            repo = PreferenceRepository(session)
            row, created = await repo.upsert(user_id)

        pref = _orm_to_domain(row)
        self._cache[user_id] = pref
        return pref, created

    def invalidate_cache(self, user_id: int) -> None:
        """
        Remove *user_id* from the in-memory cache.

        Call this when preferences are changed outside of PreferenceService
        (e.g. admin bulk-update) to ensure the next read fetches fresh data.

        Args:
            user_id: Telegram user ID to evict from cache.
        """
        self._cache.pop(user_id, None)
