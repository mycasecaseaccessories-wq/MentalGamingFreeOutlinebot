"""
User domain model.

Plain Python dataclass representing a platform user.
Not coupled to SQLAlchemy — returned by UserService and consumed by handlers.

Phase 0.4: Added first_name, last_name, status, last_active fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import Language, UserRole, UserStatus


@dataclass
class User:
    """
    Represents a platform user.

    Attributes:
        telegram_id  Unique Telegram user ID (primary external key).
        full_name    Display name from the Telegram client.
        first_name   First name from Telegram (may be None for legacy rows).
        last_name    Last name from Telegram (optional).
        username     Telegram @username, may be None or change over time.
        role         Current role determining access level.
        status       Account lifecycle status.
        language     Preferred UI language.
        is_active    False when the account is suspended (legacy flag).
        is_verified  True after identity verification.
        last_active  UTC timestamp of last bot interaction.
        created_at   UTC timestamp of first registration.
        updated_at   UTC timestamp of last profile update.
    """

    telegram_id: int
    full_name: str
    role: UserRole = UserRole.CUSTOMER
    status: UserStatus = UserStatus.ACTIVE
    language: Language = Language.ENGLISH
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    last_active: Optional[datetime] = None
    referred_by: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ── Convenience helpers ────────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        """Return True if the user holds the ADMIN role."""
        return self.role == UserRole.ADMIN

    @property
    def is_customer(self) -> bool:
        """Return True if the user is a regular customer."""
        return self.role == UserRole.CUSTOMER

    @property
    def is_banned(self) -> bool:
        """Return True if the account is permanently banned."""
        return self.status == UserStatus.BANNED

    @property
    def is_suspended(self) -> bool:
        """Return True if the account is temporarily suspended."""
        return self.status == UserStatus.SUSPENDED

    @property
    def can_use_bot(self) -> bool:
        """
        Return True when the user is allowed to interact with the bot.

        Banned and suspended users are blocked.  Inactive and pending
        users may still interact (restriction is role-dependent).
        """
        return self.status not in (UserStatus.BANNED, UserStatus.SUSPENDED)

    @property
    def display_name(self) -> str:
        """Return @username when available, otherwise full_name."""
        return f"@{self.username}" if self.username else self.full_name

    @property
    def short_name(self) -> str:
        """Return first_name, or the first token of full_name as fallback."""
        return self.first_name or self.full_name.split()[0]

    def __repr__(self) -> str:
        return (
            f"User(telegram_id={self.telegram_id}, "
            f"display_name={self.display_name!r}, "
            f"role={self.role.value}, "
            f"status={self.status.value})"
        )
