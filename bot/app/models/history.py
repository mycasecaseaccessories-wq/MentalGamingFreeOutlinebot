"""Customer-safe read DTOs for Phase 2.5 history screens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class OrderHistoryItem:
    public_order_id: str
    package_name: str
    package_type: str | None
    data_limit_gb: Decimal | None
    duration_days: int | None
    device_limit: int | None
    amount: Decimal
    currency: str
    status: str
    payment_status: str
    payment_method: str | None
    payment_reference: str | None
    created_at: datetime
    paid_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class HistoryPage:
    items: tuple
    page: int
    page_size: int
    total: int
    has_previous: bool
    has_next: bool


@dataclass(frozen=True, slots=True)
class PaymentHistoryItem:
    payment_id: str
    order_public_id: str | None
    payment_type: str
    payment_method: str | None
    amount: Decimal
    currency: str
    status: str
    reference: str | None
    created_at: datetime
    updated_at: datetime | None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentHistoryPage:
    items: tuple[PaymentHistoryItem, ...]
    page: int
    page_size: int
    total: int
    has_previous: bool
    has_next: bool
