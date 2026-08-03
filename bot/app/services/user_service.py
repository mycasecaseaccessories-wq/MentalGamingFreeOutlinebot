"""
UserService — user account management.

Responsibilities (Phase 1+):
  • Create or update a user profile on first /start.
  • Retrieve user records by Telegram ID.
  • Update role, language preference, and active status.
  • Provide helpers for admin queries (list all users, ban/unban).
"""

from __future__ import annotations

from app.models import User
from .base import BaseService


class UserService(BaseService):
    """Manages user lifecycle and profile data."""

    async def get_or_create(self, telegram_id: int, full_name: str, username: str | None = None) -> User:
        """
        Return the existing user or create a new one on first interaction.

        Args:
            telegram_id: Unique Telegram user ID.
            full_name:   Display name from the Telegram client.
            username:    Optional Telegram @username.

        Returns:
            The persisted User domain object.

        Raises:
            NotImplementedError: Until Phase 1 implementation.
        """
        # TODO (Phase 1): call UserRepository.get_by_telegram_id()
        # TODO (Phase 1): if not found, call UserRepository.create()
        raise NotImplementedError("UserService.get_or_create — Phase 1")

    async def get_by_id(self, telegram_id: int) -> User | None:
        """
        Retrieve a user by their Telegram ID.

        Returns:
            User if found, None otherwise.
        """
        # TODO (Phase 1): call UserRepository.get_by_telegram_id()
        raise NotImplementedError("UserService.get_by_id — Phase 1")

    async def set_language(self, telegram_id: int, language_code: str) -> None:
        """
        Update the user's preferred UI language.

        Args:
            telegram_id:   User to update.
            language_code: One of 'en', 'my' (see Language enum).
        """
        # TODO (Phase 1): validate language_code, call UserRepository.update()
        raise NotImplementedError("UserService.set_language — Phase 1")

    async def ban(self, telegram_id: int) -> None:
        """Deactivate a user account (admin action)."""
        # TODO (Phase 1): set is_active=False, log the action
        raise NotImplementedError("UserService.ban — Phase 1")

    async def unban(self, telegram_id: int) -> None:
        """Reactivate a previously banned user account."""
        # TODO (Phase 1): set is_active=True, log the action
        raise NotImplementedError("UserService.unban — Phase 1")
