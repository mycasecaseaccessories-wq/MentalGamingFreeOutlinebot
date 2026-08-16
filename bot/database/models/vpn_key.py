"""
VPNKeyORM — Outline access keys issued to users.

Phase 1.5 extends the read model used by the customer "My Keys" UI.
No Outline API calls or key lifecycle mutations are implemented here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class VPNKeyORM(BaseModel):
    """Issued Outline VPN access key."""

    __tablename__ = "vpn_keys"

    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        comment="FK → users.id; owner of this key",
    )
    server_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        comment="FK → servers.id",
    )
    outline_key_id: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Server-scoped key ID returned by Outline",
    )
    access_url: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Sensitive ss:// connection URL; owner-only",
    )
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data_limit_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="GB-based key allowance expressed in bytes",
    )
    used_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Last locally-known usage value; synced in Phase 4",
    )
    device_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Configured package device allowance",
    )
    package_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True,
        comment="Optional package snapshot reference",
    )
    key_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="paid",
        comment="paid | free_trial | promotion | reward | vip",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True,
        comment="VPNKeyStatus value",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Legacy compatibility flag; status is preferred for display",
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    remote_limit_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    usage_baseline_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_usage_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    limit_source: Mapped[str | None] = mapped_column(String(48), nullable=True)
    limit_source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    limit_status: Mapped[str] = mapped_column(String(24), nullable=False, default="not_applied")
    provider_limit_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    limit_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    limit_operation_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of last stored usage sync; Phase 4 populates it",
    )
