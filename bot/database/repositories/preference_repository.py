"""
PreferenceRepository — data access for the user_preferences table.

One row per user.  All methods use the telegram_id (user_id column) as
the primary lookup key, not the internal integer PK.

Phase 0.5: Full implementation — upsert, field updates, reset, bulk read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select

from database.models.user_preference import UserPreferenceORM
from .base import BaseRepository


class PreferenceRepository(BaseRepository[UserPreferenceORM, UserPreferenceORM]):
    """Handles all database operations for the user_preferences table."""

    orm_class    = UserPreferenceORM
    domain_class = UserPreferenceORM

    # ── Lookups ───────────────────────────────────────────────────────────

    async def get_by_user_id(self, user_id: int) -> Optional[UserPreferenceORM]:
        """
        Fetch the preference row for *user_id*.

        Args:
            user_id: Telegram user ID.

        Returns:
            UserPreferenceORM row, or None when not found.
        """
        stmt = select(UserPreferenceORM).where(UserPreferenceORM.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Create / upsert ───────────────────────────────────────────────────

    async def upsert(
        self,
        user_id: int,
        defaults: Optional[dict[str, Any]] = None,
    ) -> tuple[UserPreferenceORM, bool]:
        """
        Return the existing preference row or insert a new one.

        Args:
            user_id:  Telegram user ID.
            defaults: Column values applied only when creating a new row.
                      Existing rows are never overwritten by this call.

        Returns:
            Tuple of (UserPreferenceORM, created: bool).
        """
        row = await self.get_by_user_id(user_id)
        if row is not None:
            return row, False

        kwargs: dict[str, Any] = {"user_id": user_id}
        if defaults:
            kwargs.update(defaults)

        row = UserPreferenceORM(**kwargs)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        self._log.debug("created preferences for user_id=%s", user_id)
        return row, True

    # ── Field-level updates ───────────────────────────────────────────────

    async def set_field(
        self, user_id: int, key: str, value: Any
    ) -> Optional[UserPreferenceORM]:
        """
        Set a single preference field for *user_id*.

        Creates the preference row if it does not exist yet.

        Args:
            user_id: Telegram user ID.
            key:     Column name (must be a valid PreferenceKey constant).
            value:   New value to persist.

        Returns:
            Updated UserPreferenceORM row.

        Raises:
            AttributeError: If *key* is not a column on UserPreferenceORM.
        """
        if not hasattr(UserPreferenceORM, key):
            raise AttributeError(
                f"UserPreferenceORM has no column {key!r}."
            )

        row, _ = await self.upsert(user_id)
        setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return row

    async def set_fields(
        self, user_id: int, updates: dict[str, Any]
    ) -> Optional[UserPreferenceORM]:
        """
        Set multiple preference fields atomically.

        Args:
            user_id: Telegram user ID.
            updates: Dict of {column_name: new_value}.

        Returns:
            Updated UserPreferenceORM row.
        """
        for key in updates:
            if not hasattr(UserPreferenceORM, key):
                raise AttributeError(
                    f"UserPreferenceORM has no column {key!r}."
                )

        row, _ = await self.upsert(user_id)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return row

    # ── Reset ─────────────────────────────────────────────────────────────

    async def reset(self, user_id: int) -> UserPreferenceORM:
        """
        Delete the preference row and replace it with a fresh default row.

        Args:
            user_id: Telegram user ID.

        Returns:
            Newly created UserPreferenceORM row with all defaults.
        """
        row = await self.get_by_user_id(user_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

        new_row = UserPreferenceORM(user_id=user_id)
        self._session.add(new_row)
        await self._session.flush()
        await self._session.refresh(new_row)
        self._log.debug("reset preferences for user_id=%s", user_id)
        return new_row

    async def reset_field(self, user_id: int, key: str, default: Any) -> Optional[UserPreferenceORM]:
        """
        Reset a single preference field to its default value.

        Args:
            user_id:  Telegram user ID.
            key:      Column name to reset.
            default:  The default value to restore.

        Returns:
            Updated UserPreferenceORM row.
        """
        return await self.set_field(user_id, key, default)

    # ── Bulk access ───────────────────────────────────────────────────────

    async def get_users_with_notifications(self) -> List[UserPreferenceORM]:
        """
        Return all preference rows where notification_enabled = True.

        Used by the notification scheduler to build the recipient list.
        """
        stmt = select(UserPreferenceORM).where(
            UserPreferenceORM.notification_enabled.is_(True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_users_for_broadcast(self) -> List[UserPreferenceORM]:
        """
        Return all preference rows where broadcast_enabled = True.

        Used by the admin broadcast feature (Phase 2+).
        """
        stmt = select(UserPreferenceORM).where(
            UserPreferenceORM.broadcast_enabled.is_(True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
