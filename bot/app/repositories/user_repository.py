"""
UserRepository — data access for User records.

Wraps all SQL queries related to user accounts.
Returns User domain objects; never exposes raw ORM rows to callers.
"""

from __future__ import annotations

from typing import Optional

from app.models import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Handles all database operations for the User entity."""

    # model_class = UserORM   # TODO (Phase 1): assign ORM mapped class
    # domain_class = User

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Fetch a user by their unique Telegram user ID.

        Args:
            telegram_id: Telegram user identifier.

        Returns:
            User domain object, or None when not found.
        """
        # TODO (Phase 1): SELECT * FROM users WHERE telegram_id = :telegram_id
        raise NotImplementedError("UserRepository.get_by_telegram_id — Phase 1")

    async def get_all_active(self) -> list[User]:
        """Return all users where is_active = True."""
        # TODO (Phase 1): SELECT * FROM users WHERE is_active = TRUE
        raise NotImplementedError("UserRepository.get_all_active — Phase 1")

    async def count(self) -> int:
        """Return the total number of registered users."""
        # TODO (Phase 1): SELECT COUNT(*) FROM users
        raise NotImplementedError("UserRepository.count — Phase 1")
