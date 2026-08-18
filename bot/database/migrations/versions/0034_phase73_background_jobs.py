"""Phase 7.3 durable background jobs.

Revision ID: 0034_phase73_background_jobs
Revises: 0033_phase66_entitlement_redemptions
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0034_phase73_background_jobs"
down_revision = "0033_phase66_entitlement_redemptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("logical_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("payload_safe", sa.JSON(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("public_id", name="uq_background_jobs_public_id"),
        sa.UniqueConstraint("logical_key", name="uq_background_jobs_logical_key"),
    )
    op.create_index("ix_background_jobs_due", "background_jobs", ["status", "available_at"])
    op.create_index("ix_background_jobs_lease", "background_jobs", ["status", "lease_expires_at"])
    op.create_index("ix_background_jobs_type", "background_jobs", ["job_type", "status"])
    op.create_index("ix_background_jobs_correlation_id", "background_jobs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_background_jobs_correlation_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_type", table_name="background_jobs")
    op.drop_index("ix_background_jobs_lease", table_name="background_jobs")
    op.drop_index("ix_background_jobs_due", table_name="background_jobs")
    op.drop_table("background_jobs")
