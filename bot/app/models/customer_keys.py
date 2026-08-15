"""Owner-scoped read models for the My Keys UI."""

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
class CustomerKeyDetail(CustomerKeySummary):
    name: str | None = None
    device_limit: int | None = None
    created_at: datetime | None = None
    last_synced_at: datetime | None = None