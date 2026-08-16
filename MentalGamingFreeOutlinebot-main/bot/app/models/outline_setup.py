"""Shared Outline setup pipeline DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class OutlineCredentialInput:
    management_url: str
    cert_sha256: str | None = None
    source: str = "api_url"


@dataclass(frozen=True, slots=True)
class OutlineDiscoveryResult:
    host: str
    port: int | None
    provider_server_id: str | None
    outline_version: str | None
    api_compatible: bool
    existing_key_count: int | None
    metrics_available: bool
    verified_at: datetime
    safe_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutlineSetupSession:
    flow_id: str
    admin_id: int
    setup_method: str
    existing_server_id: str | None
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OutlineSetupReview:
    flow_id: str
    server_public_id: str | None
    source: str
    discovery: OutlineDiscoveryResult
    name: str | None
    country_code: str | None
    region: str | None
    paid_enabled: bool
    free_trial_enabled: bool
    vip_enabled: bool
    max_users: int | None
    traffic_limit_bytes: int | None
    priority: int
    weight: int
    credential_reference: str


@dataclass(frozen=True, slots=True)
class OutlineSetupResult:
    server_public_id: str
    secret_reference: str
    status: str
    enabled: bool
    discovery: OutlineDiscoveryResult
