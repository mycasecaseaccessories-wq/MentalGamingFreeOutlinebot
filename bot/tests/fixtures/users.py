"""Fake user domain objects for testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FakeUser:
    """Fake platform user — mirrors the PlatformUser domain model."""

    telegram_id: int = 999_000_001
    username: str | None = "testuser"
    first_name: str = "Test"
    last_name: str | None = "User"
    language: str = "en"
    role: str = "customer"
    is_active: bool = True
    is_banned: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)


def make_user(**overrides: object) -> FakeUser:
    """Return a FakeUser with any fields overridden."""
    return FakeUser(**overrides)  # type: ignore[arg-type]


def make_admin_user(**overrides: object) -> FakeUser:
    return make_user(role="admin", telegram_id=100_000_001, **overrides)


def make_banned_user(**overrides: object) -> FakeUser:
    return make_user(is_banned=True, is_active=False, **overrides)
