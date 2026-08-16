"""Authoritative multi-server registry model for Phase 3+."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ServerORM(BaseModel):
    """Server metadata and lifecycle state.

    Phase 3.1 intentionally stores metadata only. A manually registered row
    starts Unknown + Disabled and is not considered verified or production-ready.
    """

    __tablename__ = "servers"

    STATUS_UNKNOWN = "unknown"
    STATUS_ONLINE = "online"
    STATUS_OFFLINE = "offline"
    STATUS_MAINTENANCE = "maintenance"
    STATUS_DISABLED = "disabled"
    STATUS_PROVISIONING = "provisioning"
    STATUS_ARCHIVED = "archived"

    HEALTH_UNKNOWN = "unknown"
    HEALTH_OK = "ok"
    HEALTH_DEGRADED = "degraded"
    HEALTH_DOWN = "down"

    public_server_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_url: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    cert_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, default="outline")
    integration_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_UNKNOWN, index=True)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default=HEALTH_UNKNOWN, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_keys: Mapped[int | None] = mapped_column(Integer, nullable=True)

    traffic_limit_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_traffic_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    free_trial_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vip_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_server_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_endpoint_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    secret_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    credential_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outline_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_compatible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metrics_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    existing_key_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
