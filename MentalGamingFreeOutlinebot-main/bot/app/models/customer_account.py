"""Transport-neutral DTOs for Phase 1.3 customer account pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProfileSummary:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    role: str
    status: str
    language: str
    created_at: datetime | None
    last_active: datetime | None
    preferred_currency: str
    notification_enabled: bool
    broadcast_enabled: bool


@dataclass(frozen=True, slots=True)
class WalletSummary:
    wallet_id: int
    balance: Decimal
    currency: str
    is_frozen: bool


@dataclass(frozen=True, slots=True)
class TransactionSummary:
    transaction_id: int
    amount: Decimal
    currency: str
    type: str
    reference: str | None
    note: str | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class TransactionPage:
    items: tuple[TransactionSummary, ...]
    page: int
    page_size: int
    has_previous: bool
    has_next: bool
