"""Fake wallet domain objects for testing (Phase 3+)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


@dataclass
class FakeWallet:
    """Fake wallet — reflects the Wallet model that will be built in Phase 3."""

    id: int = 1
    user_id: int = 999_000_001
    balance: Decimal = field(default_factory=lambda: Decimal("0.00"))
    currency: str = "USD"
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def make_wallet(**overrides: object) -> FakeWallet:
    return FakeWallet(**overrides)  # type: ignore[arg-type]


def make_funded_wallet(amount: str = "50.00", **overrides: object) -> FakeWallet:
    return make_wallet(balance=Decimal(amount), **overrides)
