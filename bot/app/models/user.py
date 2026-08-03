"""
User domain model.

This is the canonical user representation used across the service layer.
It is framework-agnostic and does not reference any ORM or Telegram objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import Language, UserRole


@dataclass
class User:
    """
    Represents a platform user.

    Attributes:
        telegram_id    Unique Telegram user ID (primary external key).
        username       Telegram @username, may be None.
        full_name      Display name shown in the Telegram client.
        role           Current role determining access level.
        language       Preferred UI language.
        is_active      False when the account has been suspended.
        created_at     UTC timestamp of first registration.
        updated_at     UTC timestamp of last profile update.
    """

    telegram_id: int
    full_name: str
    role: UserRole = UserRole.CUSTOMER
    language: Language = Language.ENGLISH
    username: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ── Convenience helpers ────────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        """Return True if the user holds the ADMIN role."""
        return self.role == UserRole.ADMIN

    @property
    def display_name(self) -> str:
        """Return @username when available, otherwise full_name."""
        return f"@{self.username}" if self.username else self.full_name

    def __repr__(self) -> str:
        return (
            f"User(telegram_id={self.telegram_id}, "
            f"display_name={self.display_name!r}, "
            f"role={self.role.value})"
        )
