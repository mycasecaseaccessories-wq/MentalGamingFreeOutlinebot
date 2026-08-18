"""Persistent authorization state for Phase 8.1."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class AdminPrincipalORM(BaseModel):
    """One authoritative admin principal bound to one application user."""

    __tablename__ = "admin_principals"
    __table_args__ = (UniqueConstraint("user_id", name="uq_admin_principal_user"),)

    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin", index=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_privileged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bootstrap_source: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AdminSessionORM(BaseModel):
    """Short-lived server-side session bound to a principal version."""

    __tablename__ = "admin_sessions"

    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    principal_id: Mapped[int] = mapped_column(Integer, index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AdminPermissionGrantORM(BaseModel):
    """Explicit permission grant/revocation attached to one principal."""

    __tablename__ = "admin_permission_grants"
    __table_args__ = (
        UniqueConstraint("principal_id", "permission", name="uq_admin_permission_principal_key"),
    )

    principal_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    permission: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    granted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PrivilegedActionChallengeORM(BaseModel):
    """Short-lived, actor-bound, single-use critical-action challenge."""

    __tablename__ = "privileged_action_challenges"

    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    principal_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_safe_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)


class SecurityEventORM(BaseModel):
    """Safe security telemetry; never stores credentials or sensitive payloads."""

    __tablename__ = "security_events"

    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_principal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_safe_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
