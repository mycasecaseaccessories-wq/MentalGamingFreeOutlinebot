"""Transport-neutral package catalogue models for Phase 1.4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PackageSummary:
    package_id: int
    name: str
    package_type: str
    price: Decimal
    currency: str
    data_limit_gb: Decimal | None
    duration_days: int
    device_limit: int | None
    priority: str
    server_policy: str
    country: str | None
    renewable: bool
    description: str | None
    badge: str | None
    promo_label: str | None
    display_order: int


@dataclass(frozen=True, slots=True)
class PackagePage:
    items: tuple[PackageSummary, ...]
    page: int
    page_size: int
    total: int
    has_previous: bool
    has_next: bool


@dataclass(frozen=True, slots=True)
class PackageSelection:
    """Minimal server-side checkout session; never serialize full package data into callback data."""
    user_id: int
    package_id: int
    package_name: str
    package_type: str
    quoted_price: Decimal
    currency: str
    data_limit_gb: Decimal | None
    duration_days: int
    device_limit: int | None
    server_policy: str
    country: str | None
    selected_at: datetime
    expires_at: datetime
    checkout_token: str
