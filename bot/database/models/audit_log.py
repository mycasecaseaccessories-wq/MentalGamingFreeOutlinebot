"""
AuditLogORM — immutable log of admin, user, and system actions.

Every significant action in the platform writes an audit log entry.
Rows are never updated or deleted — they are the tamper-evident record.

Columns
-------
actor_id     FK → users.id of the user or admin who triggered the action.
             NULL for system-initiated events (scheduler, webhook).
action       Short action identifier (e.g. "user.ban", "key.revoke").
entity_type  Name of the affected entity class (e.g. "User", "VPNKey").
entity_id    Primary key of the affected entity row.
old_value    JSON snapshot of the entity state before the action.
new_value    JSON snapshot of the entity state after the action.
ip_address   Client IP address if available.
note         Human-readable description for the admin audit trail.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class AuditLogORM(BaseModel):
    """
    Immutable audit log entry.

    Phase 0.2: schema placeholder.
    Phase 1+:  written by services on every significant state change.

    Action naming convention
    ------------------------
    Use dot-notation: <entity>.<verb>
    Examples:
      user.created       user.banned        user.language_changed
      key.issued         key.revoked        key.limit_set
      server.added       server.removed
      wallet.credited    wallet.debited
      order.placed       order.fulfilled    order.refunded
      setting.updated
    """

    __tablename__ = "audit_logs"

    actor_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="FK → users.id of the actor. NULL for system events",
    )
    action: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="Action identifier in dot-notation: entity.verb",
    )
    entity_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Name of the affected entity class (e.g. User, VPNKey)",
    )
    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Primary key of the affected entity row",
    )
    old_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON snapshot of entity state BEFORE the action",
    )
    new_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON snapshot of entity state AFTER the action",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="Client IP address (IPv4 or IPv6) if available",
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description for the admin audit trail",
    )
