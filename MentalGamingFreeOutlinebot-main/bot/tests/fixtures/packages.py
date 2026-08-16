"""Fake VPN package domain objects for testing (Phase 2+)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


@dataclass
class FakePackage:
    """Fake VPN subscription package."""

    id: int = 1
    name: str = "Basic 30-Day"
    price: Decimal = field(default_factory=lambda: Decimal("9.99"))
    duration_days: int = 30
    data_limit_gb: float = 50.0
    is_active: bool = True
    currency: str = "USD"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def make_package(**overrides: object) -> FakePackage:
    return FakePackage(**overrides)  # type: ignore[arg-type]


def make_free_trial_package(**overrides: object) -> FakePackage:
    return make_package(
        name="Free Trial",
        price=Decimal("0.00"),
        duration_days=7,
        data_limit_gb=5.0,
        **overrides,
    )
