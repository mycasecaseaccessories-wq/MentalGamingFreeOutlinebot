"""phase72 operational alerts

Revision ID: 0038_phase72_operational_alerts
Revises: 0037_phase75_control_actions
"""

import sqlalchemy as sa
from alembic import op

revision = "0038_phase72_operational_alerts"
down_revision = "0037_phase75_control_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=160), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("component", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("safe_summary", sa.String(length=600), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("recovery_metadata_json", sa.Text(), nullable=True),
        sa.UniqueConstraint("public_id", name="uq_operational_alerts_public_id"),
        sa.UniqueConstraint("fingerprint", name="uq_operational_alerts_fingerprint"),
    )
    op.create_index(
        "ix_operational_alerts_status_type", "operational_alerts", ["status", "alert_type"]
    )
    op.create_index(
        "ix_operational_alerts_component_status", "operational_alerts", ["component", "status"]
    )
    op.create_index("ix_operational_alerts_incident_id", "operational_alerts", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_operational_alerts_incident_id", table_name="operational_alerts")
    op.drop_index("ix_operational_alerts_component_status", table_name="operational_alerts")
    op.drop_index("ix_operational_alerts_status_type", table_name="operational_alerts")
    op.drop_table("operational_alerts")
