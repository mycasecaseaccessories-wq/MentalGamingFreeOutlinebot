"""Factory for generating realistic Package test objects."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from faker import Faker

from tests.fixtures.packages import FakePackage

_faker = Faker()

_DURATIONS = [7, 30, 90, 180, 365]
_DATA_LIMITS = [5.0, 10.0, 25.0, 50.0, 100.0, 0.0]  # 0.0 = unlimited


class PackageFactory:
    _seq: int = 0

    @classmethod
    def _next_id(cls) -> int:
        cls._seq += 1
        return cls._seq

    @classmethod
    def build(cls, **overrides: Any) -> FakePackage:
        duration = random.choice(_DURATIONS)
        defaults: dict[str, Any] = {
            "id": cls._next_id(),
            "name": f"{duration}-Day VPN Package",
            "price": Decimal(str(round(random.uniform(3.0, 30.0), 2))),
            "duration_days": duration,
            "data_limit_gb": random.choice(_DATA_LIMITS),
            "is_active": True,
            "currency": "USD",
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return FakePackage(**defaults)

    @classmethod
    def build_free_trial(cls, **overrides: Any) -> FakePackage:
        return cls.build(
            name="Free Trial",
            price=Decimal("0.00"),
            duration_days=7,
            data_limit_gb=5.0,
            **overrides,
        )

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[FakePackage]:
        return [cls.build(**overrides) for _ in range(count)]
