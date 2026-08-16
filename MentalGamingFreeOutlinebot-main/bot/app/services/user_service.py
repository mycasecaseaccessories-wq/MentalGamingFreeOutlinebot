"""
UserService — user account management and authentication flow.

Responsibilities:
  • Register a user on first /start (get-or-create).
  • Retrieve and update user profiles.
  • Track last-active timestamps.
  • Change language, role, and account status.

Phase 0.4: Core auth flow implemented.
Phase 1:   Wallet creation on registration, referral tracking.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.models.enums import Language, UserRole, UserStatus
from app.models.user import User
from database.connection import DatabaseManager
from database.models.user import UserORM
from database.repositories import UserRepository

from .base import BaseService

logger = logging.getLogger(__name__)


def _orm_to_domain(row: UserORM) -> User:
    """Map a UserORM row to a User domain object."""
    return User(
        telegram_id=row.telegram_id,
        full_name=row.full_name,
        first_name=row.first_name,
        last_name=row.last_name,
        username=row.username,
        role=UserRole(row.role) if row.role else UserRole.CUSTOMER,
        status=UserStatus(row.status) if row.status else UserStatus.ACTIVE,
        language=Language(row.language) if row.language else Language.ENGLISH,
        is_active=row.is_active,
        is_verified=row.is_verified,
        last_active=row.last_active,
        referred_by=row.referred_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class UserService(BaseService):
    """Manages user lifecycle, profile data, and authentication checks."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        super().__init__(db)

    # ── Registration ──────────────────────────────────────────────────────

    async def register_user(
        self,
        telegram_id: int,
        full_name: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language: str = "en",
    ) -> tuple[User, bool]:
        """
        Register a new user or return the existing profile (get-or-create).

        Called on every /start and on the first message from a new user.
        Refreshes mutable Telegram fields (full_name, username) on each call.

        Args:
            telegram_id: Immutable Telegram user ID.
            full_name:   Display name from Telegram.
            username:    Optional @username.
            first_name:  First name from Telegram.
            last_name:   Last name from Telegram.
            language:    Default language for new users (from bot settings).

        Returns:
            Tuple of (User domain object, created: bool).
        """
        if telegram_id <= 0:
            raise ValueError("telegram_id must be a positive integer")
        full_name = (full_name or "").strip()[:255] or "Telegram User"
        username = username.strip().lstrip("@")[:64] if username else None
        first_name = first_name.strip()[:128] if first_name else None
        last_name = last_name.strip()[:128] if last_name else None

        async with self.db.session() as session:
            repo = UserRepository(session)
            existing = await repo.get_by_telegram_id(telegram_id)
            if existing is None:
                from app.hooks import HookType, hooks
                await hooks.run(
                    HookType.BEFORE_USER_REGISTER,
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )
            row, created = await repo.upsert(
                telegram_id=telegram_id,
                full_name=full_name,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language=language,
            )

        user = _orm_to_domain(row)
        if created:
            from app.events import EventType, bus
            from app.hooks import HookType, hooks
            await hooks.run(HookType.AFTER_USER_REGISTER, user=user)
            await bus.emit(
                EventType.USER_REGISTERED,
                telegram_id=telegram_id,
                username=username,
                role=user.role.value,
            )
            logger.info(
                "New user registered — telegram_id=%s username=%s",
                telegram_id, username,
            )
        else:
            from app.events import EventType, bus
            await bus.emit(
                EventType.USER_RETURNED,
                telegram_id=telegram_id,
                username=username,
                role=user.role.value,
            )
            logger.debug(
                "Returning user identified — telegram_id=%s", telegram_id
            )
        return user, created

    # ── Profile access ────────────────────────────────────────────────────

    async def get_profile(self, telegram_id: int) -> Optional[User]:
        """
        Retrieve a user profile by Telegram ID.

        Args:
            telegram_id: Telegram user identifier.

        Returns:
            User domain object, or None when not found.
        """
        async with self.db.session() as session:
            repo = UserRepository(session)
            row = await repo.get_by_telegram_id(telegram_id)
        return _orm_to_domain(row) if row else None

    async def get_or_create(
        self,
        telegram_id: int,
        full_name: str,
        username: Optional[str] = None,
    ) -> User:
        """
        Return the existing user or create a new one.

        Convenience wrapper for handlers that do not have access to
        the full Telegram User object (backward-compatible with Phase 0.1).
        """
        user, _ = await self.register_user(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
        )
        return user

    async def get_by_id(self, telegram_id: int) -> Optional[User]:
        """Alias for get_profile() — backward-compatible."""
        return await self.get_profile(telegram_id)

    # ── Profile mutations ─────────────────────────────────────────────────

    async def update_profile(
        self,
        telegram_id: int,
        full_name: Optional[str] = None,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Optional[User]:
        """
        Update mutable profile fields for a user.

        Only fields with non-None values are updated.

        Args:
            telegram_id: User to update.
            full_name:   New display name.
            username:    New @username.
            first_name:  New first name.
            last_name:   New last name.

        Returns:
            Updated User domain object, or None if user not found.
        """
        async with self.db.session() as session:
            repo = UserRepository(session)
            row = await repo.get_by_telegram_id(telegram_id)
            if row is None:
                return None
            if full_name is not None:
                row.full_name = full_name
            if username is not None:
                row.username = username
            if first_name is not None:
                row.first_name = first_name
            if last_name is not None:
                row.last_name = last_name

        logger.debug("Profile updated — telegram_id=%s", telegram_id)
        return _orm_to_domain(row)

    async def update_last_active(self, telegram_id: int) -> None:
        """
        Record that the user just interacted with the bot.

        Called by the activity middleware on every update.
        Uses a direct SQL UPDATE to minimise overhead.

        Args:
            telegram_id: User whose timestamp to refresh.
        """
        async with self.db.session() as session:
            repo = UserRepository(session)
            await repo.update_last_active(telegram_id)

    async def change_language(self, telegram_id: int, language_code: str) -> Optional[User]:
        """
        Set the user's preferred UI language.

        Args:
            telegram_id:   User to update.
            language_code: Language code ('en' or 'my').

        Returns:
            Updated User domain object, or None if not found.

        Raises:
            ValueError: If language_code is not supported.
        """
        supported = {lang.value for lang in Language}
        if language_code not in supported:
            raise ValueError(
                f"Unsupported language code {language_code!r}. "
                f"Supported: {sorted(supported)}"
            )
        async with self.db.session() as session:
            repo = UserRepository(session)
            row = await repo.update_language(telegram_id, language_code)

        if row is None:
            return None
        logger.info(
            "Language changed — telegram_id=%s language=%s", telegram_id, language_code
        )
        return _orm_to_domain(row)

    async def change_status(self, telegram_id: int, status: str) -> Optional[User]:
        """
        Change the lifecycle status of a user account.

        Args:
            telegram_id: User to update.
            status:      New UserStatus value.

        Returns:
            Updated User domain object, or None if not found.

        Raises:
            ValueError: If status is not a valid UserStatus value.
        """
        valid = {s.value for s in UserStatus}
        if status not in valid:
            raise ValueError(
                f"Invalid status {status!r}. Valid: {sorted(valid)}"
            )
        async with self.db.session() as session:
            repo = UserRepository(session)
            row = await repo.update_status(telegram_id, status)

        if row is None:
            return None
        logger.info(
            "Status changed — telegram_id=%s status=%s", telegram_id, status
        )
        return _orm_to_domain(row)

    async def change_role(self, telegram_id: int, role: str) -> Optional[User]:
        """Change a user's platform role and return the updated profile."""
        valid = {item.value for item in UserRole}
        if role not in valid:
            raise ValueError(f"Invalid role {role!r}. Valid: {sorted(valid)}")
        async with self.db.session() as session:
            repo = UserRepository(session)
            row = await repo.update_role(telegram_id, role)
        if row is None:
            return None
        logger.info("Role changed — telegram_id=%s role=%s", telegram_id, role)
        return _orm_to_domain(row)

    # ── Admin helpers ─────────────────────────────────────────────────────

    async def ban(self, telegram_id: int) -> None:
        """Permanently ban a user account."""
        await self.change_status(telegram_id, UserStatus.BANNED.value)

    async def unban(self, telegram_id: int) -> None:
        """Restore a banned user to active status."""
        await self.change_status(telegram_id, UserStatus.ACTIVE.value)

    async def set_language(self, telegram_id: int, language_code: str) -> None:
        """Alias for change_language() — backward-compatible."""
        await self.change_language(telegram_id, language_code)
