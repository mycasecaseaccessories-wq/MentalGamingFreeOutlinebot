"""
UserRepository — data access for the users table.

All SQL queries related to user accounts live here.
Returns UserORM rows (to be mapped to User domain objects in Phase 1).
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models.user import UserORM
from .base import BaseRepository


class UserRepository(BaseRepository[UserORM, UserORM]):
    """
    Handles all database operations for the users table.

    Phase 0.2: CRUD is inherited from BaseRepository.
               Custom lookup methods are stubbed here.
    Phase 1:   _to_domain() maps UserORM → User domain object.
               get_or_create() called from UserService on /start.
    """

    orm_class    = UserORM
    domain_class = UserORM  # Phase 1: change to User domain model.

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserORM]:
        """
        Fetch a user by their unique Telegram user ID.

        Args:
            telegram_id: Telegram user identifier.

        Returns:
            UserORM row, or None when not found.
        """
        stmt = select(UserORM).where(UserORM.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[UserORM]:
        """
        Fetch a user by their Telegram @username (case-insensitive).

        Returns:
            UserORM row, or None.
        """
        stmt = select(UserORM).where(
            UserORM.username.ilike(username.lstrip("@"))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[UserORM]:
        """Return all users where is_active = True."""
        stmt = select(UserORM).where(UserORM.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_role(self, role: str) -> List[UserORM]:
        """
        Return all users with the given role.

        Args:
            role: Role value string (e.g. "admin", "customer").
        """
        stmt = select(UserORM).where(UserORM.role == role)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        telegram_id: int,
        full_name: str,
        username: Optional[str] = None,
        language: str = "en",
    ) -> UserORM:
        """
        Return the existing user or insert a new one (get-or-create).

        Args:
            telegram_id: Immutable Telegram user ID.
            full_name:   Display name from Telegram.
            username:    Optional @username.
            language:    Default language code for new users.

        Returns:
            Existing or newly created UserORM row.
        """
        row = await self.get_by_telegram_id(telegram_id)
        if row is not None:
            # Update mutable fields that may have changed in Telegram.
            row.full_name = full_name
            row.username  = username
            await self._session.flush()
            return row
        return await self.create(  # type: ignore[return-value]
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            language=language,
        )
