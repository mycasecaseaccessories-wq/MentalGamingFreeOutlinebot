"""Durable backup metadata; artifact bytes live in a provider, never in this table."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
    CORRUPTED = "corrupted"
    EXPIRED = "expired"
    DELETED = "deleted"


class BackupType(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    PRE_MIGRATION = "pre_migration"
    PRE_DEPLOYMENT = "pre_deployment"
    EMERGENCY = "emergency"
    RESTORE_TEST = "restore_test"


class RestoreTestStatus(str, Enum):
    NOT_RUN = "not_run"
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class BackupRecordORM(BaseModel):
    __tablename__ = "backup_records"
    __table_args__ = (
        Index("ix_backup_records_status_created", "status", "created_at"),
        Index("ix_backup_records_expires_at", "expires_at"),
        Index("ix_backup_records_job_id", "job_id"),
    )

    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    backup_type: Mapped[str] = mapped_column(String(32), default=BackupType.AUTOMATIC.value, index=True)
    database_engine: Mapped[str] = mapped_column(String(32), default="unknown")
    status: Mapped[str] = mapped_column(String(24), default=BackupStatus.PENDING.value, index=True)
    storage_provider: Mapped[str] = mapped_column(String(48), default="local")
    storage_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checksum_algorithm: Mapped[str] = mapped_column(String(16), default="sha256")
    encrypted: Mapped[bool] = mapped_column(default=False)
    encryption_key_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), default=BackupStatus.PENDING.value)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restore_test_status: Mapped[str] = mapped_column(String(24), default=RestoreTestStatus.NOT_RUN.value)
    restore_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_class: Mapped[str] = mapped_column(String(24), default="daily")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(96), nullable=True)
    manifest_json: Mapped[str] = mapped_column(Text, default="{}")
