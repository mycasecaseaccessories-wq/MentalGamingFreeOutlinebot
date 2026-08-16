"""
UserRepository — data access for the users table.

All SQL queries related to user accounts live here.
Returns UserORM rows (to be mapped to User domain objects by UserService).

Phase 0.2: CRUD inherited; lookup helpers stubbed.
Phase 0.4: Full implementations for auth flow: get_by_telegram_id,
           upsert, update_last_active, update_status, update_language,
           update_role, get_by_status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update as sa_update

from database.models.user import UserORM
from .base import BaseRepository


class UserRepository(BaseRepository[UserORM, UserORM]):
    """
    Handles all database operations for the users table.

    Phase 0.4: Full implementations wired to the UserService auth flow.
    """

    orm_class    = UserORM
    domain_class = UserORM

    # ── Lookups ───────────────────────────────────────────────────────────

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserORM]:
        """
        Fetch a user by their unique Telegram user ID.

        Args:
            telegram_id: Immutable Telegram user identifier.

        Returns:
            UserORM row, or None when not found.
        """
        stmt = select(UserORM).where(UserORM.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[UserORM]:
        """
        Fetch a user by Telegram @username (case-insensitive).

        Args:
            username: Handle with or without the '@' prefix.

        Returns:
            UserORM row, or None.
        """
        stmt = select(UserORM).where(
            UserORM.username.ilike(username.lstrip("@"))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[UserORM]:
        """Return all users where status = 'active'."""
        stmt = select(UserORM).where(UserORM.status == "active")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_role(self, role: str) -> List[UserORM]:
        """
        Return all users with the given role.

        Args:
            role: Role value string (e.g. 'admin', 'customer').
        """
        stmt = select(UserORM).where(UserORM.role == role)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> List[UserORM]:
        """
        Return all users with the given status.

        Args:
            status: UserStatus value (e.g. 'active', 'banned').
        """
        stmt = select(UserORM).where(UserORM.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Create / upsert ───────────────────────────────────────────────────

    async def upsert(
        self,
        telegram_id: int,
        full_name: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language: str = "en",
        role: str = "customer",
    ) -> tuple[UserORM, bool]:
        """
        Return the existing user or insert a new one (get-or-create).

        Args:
            telegram_id: Immutable Telegram user ID.
            full_name:   Display name from Telegram.
            username:    Optional @username.
            first_name:  First name from Telegram.
            last_name:   Last name from Telegram.
            language:    Default language code for new users.
            role:        Default role for new users.

        Returns:
            Tuple of (UserORM row, created: bool).
            created is True when a new row was inserted.
        """
        row = await self.get_by_telegram_id(telegram_id)
        if row is not None:
            # Refresh mutable fields that may change between sessions.
            updated = False
            if row.full_name != full_name:
                row.full_name = full_name
                updated = True
            if row.username != username:
                row.username = username
                updated = True
            if row.first_name != first_name:
                row.first_name = first_name
                updated = True
            if row.last_name != last_name:
                row.last_name = last_name
                updated = True
            if updated:
                await self._session.flush()
            return row, False

        row = await self.create(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language=language,
            role=role,
            status="active",
            is_active=True,
            is_verified=False,
        )
        return row, True

    # ── Updates ───────────────────────────────────────────────────────────

    async def update_last_active(self, telegram_id: int) -> None:
        """
        Stamp the last_active column with the current UTC time.

        Uses a direct UPDATE to avoid a SELECT + UPDATE round-trip.

        Args:
            telegram_id: User to update.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            sa_update(UserORM)
            .where(UserORM.telegram_id == telegram_id)
            .values(last_active=now, updated_at=now)
        )
        await self._session.execute(stmt)

    async def update_status(self, telegram_id: int, status: str) -> Optional[UserORM]:
        """
        Change the account status for a user.

        Also syncs the legacy is_active flag:
          active   → is_active = True
          others   → is_active = False

        Args:
            telegram_id: User to update.
            status:      New UserStatus value.

        Returns:
            Updated UserORM row, or None if user not found.
        """
        row = await self.get_by_telegram_id(telegram_id)
        if row is None:
            return None
        row.status = status
        row.is_active = (status == "active")
        await self._session.flush()
        return row

    async def update_language(self, telegram_id: int, language: str) -> Optional[UserORM]:
        """
        Set the user's preferred UI language.

        Args:
            telegram_id: User to update.
            language:    Language code ('en' or 'my').

        Returns:
            Updated UserORM row, or None if not found.
        """
        row = await self.get_by_telegram_id(telegram_id)
        if row is None:
            return None
        row.language = language
        await self._session.flush()
        return row

    async def update_role(self, telegram_id: int, role: str) -> Optional[UserORM]:
        """
        Change the role assigned to a user.

        Args:
            telegram_id: User to update.
            role:        New UserRole value.

        Returns:
            Updated UserORM row, or None if not found.
        """
        row = await self.get_by_telegram_id(telegram_id)
        if row is None:
            return None
        row.role = role
        await self._session.flush()
        return row
