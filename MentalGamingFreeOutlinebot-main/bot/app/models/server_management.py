"""Customer/admin-safe server management DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ServerItem:
    public_server_id: str
    name: str
    display_name: str | None
    host: str | None
    provider_type: str
    integration_type: str
    region: str | None
    country_code: str | None
    country_name: str | None
    status: str
    health_status: str
    enabled: bool
    maintenance_mode: bool
    priority: int
    weight: int
    max_users: int | None
    current_users: int
    max_keys: int | None
    traffic_limit_bytes: int | None
    used_traffic_bytes: int
    free_trial_enabled: bool
    paid_enabled: bool
    vip_enabled: bool
    last_health_check_at: datetime | None
    last_sync_at: datetime | None
    archived_at: datetime | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class ServerPage:
    items: tuple[ServerItem, ...]
    page: int
    page_size: int
    total: int
    has_previous: bool
    has_next: bool

@dataclass(frozen=True, slots=True)
class ServerMutation:
    server: ServerItem
    changed: bool = True
    idempotent: bool = False
