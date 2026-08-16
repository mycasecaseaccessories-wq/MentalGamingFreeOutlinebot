"""
SettingsService — runtime configuration & feature-flag access layer.

Responsibilities:
  • Load settings from the database on demand.
  • Cache all settings in memory for fast reads.
  • Provide typed get/set/delete helpers with value validation.
  • Seed default settings and feature flags on first startup.
  • Support category-based queries for the future admin panel.

Usage:
    from app.services import SettingsService
    from config.feature_flags import FeatureFlags

    svc = SettingsService(db)
    await svc.seed_defaults()               # once at startup

    # Read a value
    maintenance = await svc.get(FeatureFlags.ENABLE_MAINTENANCE, default=False)

    # Write a value (and update cache)
    await svc.set("vpn_max_devices", 5, type_="int")

    # Flush and rebuild cache from DB
    await svc.reload_cache()

Phase 0.3: Caching, validation, seeding, category queries.
Phase 2:   Wire into admin panel handlers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from database.connection import DatabaseManager
from database.repositories import SettingsRepository
from .base import BaseService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_and_coerce(value: Any, type_: str) -> str:
    """
    Validate *value* against *type_* and return a string-serialised form.

    Supported types:
        str   — any string value
        int   — must be convertible to int
        float — must be convertible to float
        bool  — True/False, 1/0, or "true"/"false" strings
        json  — must be JSON-serialisable
        list  — must be a list (serialised as JSON)

    Raises:
        ValueError: If the value is incompatible with the requested type.
    """
    type_ = type_.strip().lower()

    if type_ == "str":
        return str(value)

    if type_ == "int":
        try:
            return str(int(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Expected an integer value, got {value!r}."
            ) from exc

    if type_ == "float":
        try:
            return str(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Expected a float value, got {value!r}."
            ) from exc

    if type_ == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return "true" if value else "false"
        if isinstance(value, str):
            if value.strip().lower() in {"true", "1", "yes"}:
                return "true"
            if value.strip().lower() in {"false", "0", "no"}:
                return "false"
        raise ValueError(
            f"Expected a boolean value (true/false), got {value!r}."
        )

    if type_ == "json":
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Value is not JSON-serialisable: {value!r}."
            ) from exc

    if type_ == "list":
        if not isinstance(value, list):
            raise ValueError(
                f"Expected a list, got {type(value).__name__!r}."
            )
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"List contains non-serialisable elements: {value!r}."
            ) from exc

    raise ValueError(
        f"Unknown type hint {type_!r}. "
        "Allowed: str | int | float | bool | json | list"
    )


def _cast_value(raw: str, type_: str) -> Any:
    """
    Cast a string value from the database back to its Python type.

    Returns *raw* unchanged when casting fails (safe fallback).
    """
    type_ = type_.strip().lower()
    try:
        if type_ == "int":
            return int(raw)
        if type_ == "float":
            return float(raw)
        if type_ == "bool":
            return raw.strip().lower() in {"true", "1", "yes"}
        if type_ in {"json", "list"}:
            return json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        pass
    return raw


# ---------------------------------------------------------------------------
# SettingsService
# ---------------------------------------------------------------------------

class SettingsService(BaseService):
    """
    Service for reading and writing runtime configuration settings.

    The service maintains a flat in-memory cache keyed by setting key.
    The cache is populated lazily on the first read and can be refreshed
    via reload_cache().

    Attributes:
        _cache  Dict mapping setting key → typed Python value.
        _loaded Flag that tracks whether the cache has been populated.
    """

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        super().__init__(db)
        self._cache: dict[str, Any] = {}
        self._loaded: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Return the typed value for *key*.

        Loads the cache on first call.  Returns *default* when the key is
        not present in the database.

        Args:
            key:     Setting key (e.g. 'feature_enable_wallet').
            default: Value returned when the key does not exist.

        Returns:
            Typed Python value (int, float, bool, list, dict, or str).
        """
        await self._ensure_cache_loaded()
        if key in self._cache:
            return self._cache[key]
        # Fallback to DB (handles keys inserted by other processes)
        async with self.db.session() as session:
            repo = SettingsRepository(session)
            value = await repo.get_value(key, default=None)
        if value is None:
            return default
        self._cache[key] = value
        return value

    async def set(
        self,
        key: str,
        value: Any,
        *,
        type_: str = "str",
        category: Optional[str] = None,
        description: Optional[str] = None,
        is_public: bool = False,
    ) -> None:
        """
        Persist *value* for *key* and update the in-memory cache.

        Validates the value against *type_* before writing.
        Creates the row if absent; updates it if it exists.

        Args:
            key:         Setting key.
            value:       New value (must match *type_*).
            type_:       One of: str | int | float | bool | json | list.
            category:    Admin panel category slug (see SettingCategory).
            description: Human-readable label (admin panel only).
            is_public:   Whether non-admin code may read this key.

        Raises:
            ValueError: If the value fails type validation.
        """
        raw = _validate_and_coerce(value, type_)

        async with self.db.session() as session:
            repo = SettingsRepository(session)
            row = await repo.get(key)
            if row is None:
                await repo.create(
                    key=key,
                    value=raw,
                    type=type_,
                    category=category,
                    description=description,
                    is_public=is_public,
                )
            else:
                kwargs: dict[str, Any] = {"value": raw, "type": type_}
                if category is not None:
                    kwargs["category"] = category
                if description is not None:
                    kwargs["description"] = description
                await repo.update(row.id, **kwargs)

        # Update cache with typed value
        self._cache[key] = _cast_value(raw, type_)
        logger.debug("Setting updated: key=%s type=%s", key, type_)

    async def delete(self, key: str) -> bool:
        """
        Remove a setting from the database and the cache.

        Args:
            key: Setting key to delete.

        Returns:
            True if the row existed and was deleted; False otherwise.
        """
        async with self.db.session() as session:
            repo = SettingsRepository(session)
            row = await repo.get(key)
            if row is None:
                return False
            await repo.delete(row.id)

        self._cache.pop(key, None)
        logger.debug("Setting deleted: key=%s", key)
        return True

    async def exists(self, key: str) -> bool:
        """
        Return True if the setting key exists in the database.

        Args:
            key: Setting key to check.
        """
        await self._ensure_cache_loaded()
        if key in self._cache:
            return True
        async with self.db.session() as session:
            repo = SettingsRepository(session)
            row = await repo.get(key)
        return row is not None

    async def reload_cache(self) -> None:
        """
        Flush the in-memory cache and rebuild it from the database.

        Call this after bulk settings imports or external DB changes.
        """
        self._cache.clear()
        self._loaded = False
        await self._ensure_cache_loaded()
        logger.info(
            "Settings cache reloaded — %d entries", len(self._cache)
        )

    async def get_category(self, category: str) -> dict[str, Any]:
        """
        Return all settings that belong to *category* as a key→value dict.

        Args:
            category: Category slug (see SettingCategory in config.defaults).

        Returns:
            Dict mapping setting key to typed Python value.
        """
        async with self.db.session() as session:
            repo = SettingsRepository(session)
            rows = await repo.list_by_category(category)

        result: dict[str, Any] = {}
        for row in rows:
            result[row.key] = _cast_value(row.value, row.type or "str")
        return result

    async def seed_defaults(self) -> None:
        """
        Insert default settings and feature flags that are not yet in the DB.

        Safe to call on every startup — existing rows are never overwritten.

        Imports DEFAULT_SETTINGS and FEATURE_FLAG_DEFAULTS from the config
        layer and upserts only missing keys.
        """
        from config.defaults import DEFAULT_SETTINGS
        from config.feature_flags import FEATURE_FLAG_DEFAULTS, FeatureFlags

        seeded = 0

        async with self.db.session() as session:
            repo = SettingsRepository(session)

            # ── General / runtime defaults ─────────────────────────────────
            for entry in DEFAULT_SETTINGS:
                if await repo.get(entry["key"]) is None:
                    await repo.create(
                        key=entry["key"],
                        value=_validate_and_coerce(entry["value"], entry["type"]),
                        type=entry["type"],
                        category=entry.get("category"),
                        description=entry.get("description"),
                        is_public=entry.get("is_public", False),
                    )
                    seeded += 1

            # ── Feature flags ──────────────────────────────────────────────
            for key, meta in FEATURE_FLAG_DEFAULTS.items():
                if await repo.get(key) is None:
                    await repo.create(
                        key=key,
                        value=_validate_and_coerce(meta["value"], "bool"),
                        type="bool",
                        category="features",
                        description=meta.get("description"),
                        is_public=meta.get("is_public", False),
                    )
                    seeded += 1

        if seeded:
            logger.info("Seeded %d default settings into the database.", seeded)
        else:
            logger.debug("Settings seed: all defaults already present.")

        # Rebuild cache after seeding
        await self.reload_cache()

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _ensure_cache_loaded(self) -> None:
        """Load all settings into the cache if not already loaded."""
        if self._loaded:
            return
        async with self.db.session() as session:
            repo = SettingsRepository(session)
            rows = await repo.list_all()
        for row in rows:
            self._cache[row.key] = _cast_value(row.value, row.type or "str")
        self._loaded = True
        logger.debug(
            "Settings cache populated — %d entries", len(self._cache)
        )
