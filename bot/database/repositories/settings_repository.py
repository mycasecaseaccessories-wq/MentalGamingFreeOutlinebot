"""
SettingsRepository — data access for the settings table.

Provides typed get/set helpers for the key-value configuration store.
SettingsService (Phase 2) wraps this with caching.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select

from database.models.setting import SettingORM
from .base import BaseRepository


class SettingsRepository(BaseRepository[SettingORM, SettingORM]):
    """
    Handles all database operations for the settings table.

    Phase 0.2: CRUD inherited; typed helpers stubbed.
    Phase 2:   SettingsService wraps get/set with in-memory caching.
               Admin panel calls set() to update runtime configuration.
    """

    orm_class    = SettingORM
    domain_class = SettingORM

    async def get(self, key: str) -> Optional[SettingORM]:
        """
        Fetch a setting row by its unique key.

        Args:
            key: Setting identifier (e.g. "force_join_enabled").

        Returns:
            SettingORM row, or None if the key does not exist.
        """
        stmt = select(SettingORM).where(SettingORM.key == key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_value(self, key: str, default: Any = None) -> Any:
        """
        Return the typed Python value for the given key.

        Applies the type cast defined in the setting row:
          str   → plain string
          int   → int()
          float → float()
          bool  → True when value.lower() in {"true", "1", "yes"}
          json  → json.loads()

        Args:
            key:     Setting key.
            default: Returned when the key does not exist.
        """
        row = await self.get(key)
        if row is None:
            return default
        raw   = row.value
        vtype = (row.type or "str").strip().lower()
        try:
            if vtype == "int":
                return int(raw)
            if vtype == "float":
                return float(raw)
            if vtype == "bool":
                return raw.strip().lower() in {"true", "1", "yes"}
            if vtype == "json":
                return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        return raw

    async def set(self, key: str, value: Any, type_: str = "str") -> SettingORM:
        """
        Upsert a setting.

        Creates the row if absent; updates value and type if it exists.

        Args:
            key:    Setting key.
            value:  New value (will be str()-coerced for storage).
            type_:  Value type hint: str | int | float | bool | json.
        """
        if type_ == "json":
            raw = json.dumps(value)
        else:
            raw = str(value)

        row = await self.get(key)
        if row is None:
            return await self.create(key=key, value=raw, type=type_)  # type: ignore[return-value]
        return await self.update(row.id, value=raw, type=type_)  # type: ignore[return-value]

    async def list_public(self) -> list[SettingORM]:
        """Return all settings marked as is_public = True."""
        stmt = select(SettingORM).where(SettingORM.is_public.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
