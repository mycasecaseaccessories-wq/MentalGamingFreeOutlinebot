"""Phase 7.4 backup and disaster-recovery metadata.

Revision ID: 0035_phase74_backup_records
Revises: 0034_phase73_background_jobs
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0035_phase74_backup_records"
down_revision = "0034_phase73_background_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("backup_type", sa.String(length=32), nullable=False, server_default="automatic"),
        sa.Column("database_engine", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("storage_provider", sa.String(length=48), nullable=False, server_default="local"),
        sa.Column("storage_reference", sa.String(length=512), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("checksum_algorithm", sa.String(length=16), nullable=False, server_default="sha256"),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encryption_key_version", sa.String(length=64), nullable=True),
        sa.Column("verification_status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restore_test_status", sa.String(length=24), nullable=False, server_default="not_run"),
        sa.Column("restore_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_class", sa.String(length=24), nullable=False, server_default="daily"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("safe_error_code", sa.String(length=96), nullable=True),
        sa.Column("manifest_json", sa.Text(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("public_id", name="uq_backup_records_public_id"),
    )
    op.create_index("ix_backup_records_status_created", "backup_records", ["status", "created_at"])
    op.create_index("ix_backup_records_expires_at", "backup_records", ["expires_at"])
    op.create_index("ix_backup_records_job_id", "backup_records", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_backup_records_job_id", table_name="backup_records")
    op.drop_index("ix_backup_records_expires_at", table_name="backup_records")
    op.drop_index("ix_backup_records_status_created", table_name="backup_records")
    op.drop_table("backup_records")
