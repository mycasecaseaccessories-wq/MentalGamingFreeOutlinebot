"""Transport-neutral DTOs for Phase 1.5 customer VPN key pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CustomerKeySummary:
    key_id: int
    key_type: str
    status: str
    package_name: str | None
    server_name: str | None
    country: str | None
    data_limit_bytes: int | None
    used_bytes: int
    remaining_bytes: int | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class CustomerKeyDetail:
    key_id: int
    key_type: str
    status: str
    name: str | None
    package_name: str | None
    server_name: str | None
    country: str | None
    data_limit_bytes: int | None
    used_bytes: int
    remaining_bytes: int | None
    device_limit: int | None
    created_at: datetime | None
    expires_at: datetime | None
    last_synced_at: datetime | None


@dataclass(frozen=True, slots=True)
class KeyUsage:
    key_id: int
    data_limit_bytes: int | None
    used_bytes: int
    remaining_bytes: int | None
    percentage: float | None
    last_synced_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    key_id: int
    access_url: str
    server_name: str | None
    country: str | None
    status: str


@dataclass(frozen=True, slots=True)
class CustomerKeyPage:
    items: tuple[CustomerKeySummary, ...]
    page: int
    page_size: int
    has_previous: bool
    has_next: bool
    total: int
