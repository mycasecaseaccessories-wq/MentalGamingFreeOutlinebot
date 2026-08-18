from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class BackgroundJobStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class BackgroundJobORM(BaseModel):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("logical_key", name="uq_background_jobs_logical_key"),
        Index("ix_background_jobs_due", "status", "available_at"),
        Index("ix_background_jobs_lease", "status", "lease_expires_at"),
        Index("ix_background_jobs_type", "job_type", "status"),
    )

    JOB_VPN_EXPIRATION = "vpn_expiration"
    JOB_VPN_LIFECYCLE_SYNC = "vpn_lifecycle_sync"
    JOB_FREE_TRIAL_EXPIRATION = "free_trial_expiration"
    JOB_ENTITLEMENT_EXPIRATION = "entitlement_expiration"
    JOB_PROMO_EXPIRATION = "promo_expiration"
    JOB_MISSION_ROLLOVER = "mission_rollover"
    JOB_PAYMENT_TIMEOUT = "payment_timeout"
    JOB_ORDER_EXPIRATION = "order_expiration"
    JOB_REWARD_RETRY = "reward_retry"
    JOB_REWARD_RECONCILIATION = "reward_reconciliation"
    JOB_GROWTH_RECONCILIATION = "growth_reconciliation"
    JOB_VPN_RECOVERY = "vpn_recovery"
    JOB_STALE_OPERATION_RECOVERY = "stale_operation_recovery"
    JOB_HEALTH_CHECK = "health_check"
    JOB_ALERT_EVALUATION = "alert_evaluation"
    JOB_ALERT_REMINDER = "alert_reminder"
    JOB_BACKUP_CREATION = "backup_creation"
    JOB_BACKUP_RETENTION = "backup_retention"
    JOB_BACKUP_RESTORE_TEST = "backup_restore_test"
    JOB_MAINTENANCE_ACTIVATION = "maintenance_activation"
    JOB_MAINTENANCE_END = "maintenance_end"
    JOB_MAINTENANCE_REMINDER = "maintenance_reminder"
    JOB_MAINTENANCE_RECOVERY_CHECK = "maintenance_recovery_check"

    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    logical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=BackgroundJobStatus.PENDING.value, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    payload_safe: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
