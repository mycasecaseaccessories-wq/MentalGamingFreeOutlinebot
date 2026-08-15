"""Read-only package catalogue DTOs."""

from __future__ import annotations

from dataclasses import dataclass
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
    user_id: int
    package_id: int
    package_name: str
    quoted_price: Decimal
    currency: str