"""Factory for generating realistic Wallet test objects."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from faker import Faker

from tests.fixtures.wallets import FakeWallet

_faker = Faker()


class WalletFactory:
    _seq: int = 0

    @classmethod
    def _next_id(cls) -> int:
        cls._seq += 1
        return cls._seq

    @classmethod
    def build(cls, **overrides: Any) -> FakeWallet:
        defaults: dict[str, Any] = {
            "id": cls._next_id(),
            "user_id": 999_000_001,
            "balance": Decimal("0.00"),
            "currency": "USD",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return FakeWallet(**defaults)

    @classmethod
    def build_funded(cls, amount: str = "50.00", **overrides: Any) -> FakeWallet:
        return cls.build(balance=Decimal(amount), **overrides)

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[FakeWallet]:
        return [cls.build(**overrides) for _ in range(count)]
