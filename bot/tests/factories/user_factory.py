"""Factory for generating realistic PlatformUser test objects."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from faker import Faker

from tests.fixtures.users import FakeUser

_faker = Faker()
try:
    _faker_my = Faker("my_MM")
except AttributeError:
    # Faker installations differ in whether the Myanmar locale provider is
    # bundled.  Tests only need deterministic names, not locale-specific data.
    _faker_my = _faker


class UserFactory:
    """Generate FakeUser instances with realistic or seeded data."""

    _seq: int = 0

    @classmethod
    def _next_id(cls) -> int:
        cls._seq += 1
        return 900_000_000 + cls._seq

    @classmethod
    def build(cls, **overrides: Any) -> FakeUser:
        """Create a single FakeUser with faker-generated defaults."""
        defaults: dict[str, Any] = {
            "telegram_id": cls._next_id(),
            "username": _faker.user_name()[:32],
            "first_name": _faker.first_name(),
            "last_name": _faker.last_name() if random.random() > 0.3 else None,
            "language": random.choice(["en", "my"]),
            "role": "customer",
            "is_active": True,
            "is_banned": False,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return FakeUser(**defaults)

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[FakeUser]:
        return [cls.build(**overrides) for _ in range(count)]

    @classmethod
    def build_admin(cls, **overrides: Any) -> FakeUser:
        return cls.build(role="admin", **overrides)

    @classmethod
    def build_banned(cls, **overrides: Any) -> FakeUser:
        return cls.build(is_banned=True, is_active=False, **overrides)

    @classmethod
    def build_myanmar_user(cls, **overrides: Any) -> FakeUser:
        return cls.build(language="my", **overrides)

    @classmethod
    def reset(cls) -> None:
        """Reset the sequence counter — call between test modules if needed."""
        cls._seq = 0
