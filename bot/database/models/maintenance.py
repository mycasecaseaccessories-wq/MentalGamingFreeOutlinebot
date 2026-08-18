"""Durable typed maintenance windows and operational incidents."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class MaintenanceState(StrEnum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    READ_ONLY = "read_only"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


class MaintenanceScope(StrEnum):
    GLOBAL = "global"
    VPN_PROVISIONING = "vpn_provisioning"
    VPN_LIFECYCLE = "vpn_lifecycle"
    PAYMENTS = "payments"
    ORDERS = "orders"
    WALLET_WRITE = "wallet_write"
    FREE_TRIAL = "free_trial"
    REFERRALS = "referrals"
    MISSIONS = "missions"
    PROMOS = "promos"
    REWARDS = "rewards"
    ENTITLEMENTS = "entitlements"
    NOTIFICATIONS = "notifications"
    BACKGROUND_JOBS = "background_jobs"
    ADMIN_OPERATIONS = "admin_operations"
    BACKUP = "backup"


class MaintenanceWindowStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    ENDING = "ending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MaintenanceReason(StrEnum):
    PLANNED_MAINTENANCE = "planned_maintenance"
    PROVIDER_OUTAGE = "provider_outage"
    DATABASE_DEGRADED = "database_degraded"
    PAYMENT_OUTAGE = "payment_outage"
    VPN_PROVIDER_OUTAGE = "vpn_provider_outage"
    SECURITY_RESPONSE = "security_response"
    RESTORE_RECOVERY = "restore_recovery"
    DEPLOYMENT = "deployment"
    OPERATOR_ACTION = "operator_action"


class AutoEndPolicy(StrEnum):
    AUTO_END_IF_HEALTHY = "auto_end_if_healthy"
    REQUIRE_ADMIN_APPROVAL = "require_admin_approval"
    AUTO_END = "auto_end"


class MaintenanceWindowORM(BaseModel):
    __tablename__ = "maintenance_windows"
    __table_args__ = (
        Index("ix_maintenance_windows_scope_status", "scope", "status"),
        Index("ix_maintenance_windows_starts_ends", "starts_at", "expected_ends_at"),
        Index("ix_maintenance_windows_incident", "incident_id"),
    )

    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default=MaintenanceState.MAINTENANCE.value)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=MaintenanceWindowStatus.SCHEDULED.value)
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False, default=MaintenanceReason.OPERATOR_ACTION.value)
    customer_message_key: Mapped[str | None] = mapped_column(String(96), nullable=True)
    customer_message_text: Mapped[str | None] = mapped_column(String(600), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    ended_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled: Mapped[bool] = mapped_column(default=True, nullable=False)
    alert_suppression_policy: Mapped[str] = mapped_column(String(40), nullable=False, default="scoped")
    auto_end_policy: Mapped[str] = mapped_column(String(32), nullable=False, default=AutoEndPolicy.REQUIRE_ADMIN_APPROVAL.value)
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MaintenanceActionORM(BaseModel):
    """Durable operational control action for idempotency, audit, and throttling."""
    __tablename__ = "maintenance_actions"
    __table_args__ = (
        Index("ix_maintenance_actions_actor_created", "actor_id", "created_at"),
        Index("ix_maintenance_actions_window_action", "window_id", "action"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    window_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    result_code: Mapped[str] = mapped_column(String(48), nullable=False, default="accepted")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class CustomerImpact(StrEnum):
    NONE = "none"
    MINOR = "minor"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"


class OperationalIncidentORM(BaseModel):
    __tablename__ = "operational_incidents"
    __table_args__ = (
        Index("ix_operational_incidents_status_severity", "status", "severity"),
        Index("ix_operational_incidents_started_resolved", "started_at", "resolved_at"),
        Index("ix_operational_incidents_maintenance", "maintenance_window_id"),
    )

    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default=IncidentSeverity.WARNING.value)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=IncidentStatus.OPEN.value)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maintenance_window_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_alert_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_impact: Mapped[str] = mapped_column(String(24), nullable=False, default=CustomerImpact.NONE.value)
    safe_summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    internal_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
