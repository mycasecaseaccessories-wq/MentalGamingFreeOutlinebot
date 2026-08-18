"""Phase 7.5 maintenance windows and operational incidents."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0036_phase75_maintenance_incidents"
down_revision = "0035_phase74_backup_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="maintenance"),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("reason_code", sa.String(40), nullable=False, server_default="operator_action"),
        sa.Column("customer_message_key", sa.String(96), nullable=True),
        sa.Column("customer_message_text", sa.String(600), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("ended_by", sa.Integer(), nullable=True),
        sa.Column("scheduled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("alert_suppression_policy", sa.String(40), nullable=False, server_default="scoped"),
        sa.Column("auto_end_policy", sa.String(32), nullable=False, server_default="require_admin_approval"),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("public_id", name="uq_maintenance_windows_public_id"),
    )
    op.create_index("ix_maintenance_windows_scope_status", "maintenance_windows", ["scope", "status"])
    op.create_index("ix_maintenance_windows_starts_ends", "maintenance_windows", ["starts_at", "expected_ends_at"])
    op.create_index("ix_maintenance_windows_incident", "maintenance_windows", ["incident_id"])

    op.create_table(
        "operational_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("incident_type", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_admin_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_window_id", sa.Integer(), nullable=True),
        sa.Column("primary_alert_id", sa.Integer(), nullable=True),
        sa.Column("customer_impact", sa.String(24), nullable=False, server_default="none"),
        sa.Column("safe_summary", sa.String(600), nullable=False, server_default=""),
        sa.Column("internal_reference", sa.Text(), nullable=True),
        sa.UniqueConstraint("public_id", name="uq_operational_incidents_public_id"),
    )
    op.create_index("ix_operational_incidents_status_severity", "operational_incidents", ["status", "severity"])
    op.create_index("ix_operational_incidents_started_resolved", "operational_incidents", ["started_at", "resolved_at"])
    op.create_index("ix_operational_incidents_maintenance", "operational_incidents", ["maintenance_window_id"])


def downgrade() -> None:
    op.drop_index("ix_operational_incidents_maintenance", table_name="operational_incidents")
    op.drop_index("ix_operational_incidents_started_resolved", table_name="operational_incidents")
    op.drop_index("ix_operational_incidents_status_severity", table_name="operational_incidents")
    op.drop_table("operational_incidents")
    op.drop_index("ix_maintenance_windows_incident", table_name="maintenance_windows")
    op.drop_index("ix_maintenance_windows_starts_ends", table_name="maintenance_windows")
    op.drop_index("ix_maintenance_windows_scope_status", table_name="maintenance_windows")
    op.drop_table("maintenance_windows")
