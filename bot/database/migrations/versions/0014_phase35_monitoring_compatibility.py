"""Phase 3.5 monitoring compatibility revision.

The monitoring columns were introduced by the Phase 3.1/3.2 server schema in
this consolidated tree. This no-op revision preserves the historical Alembic
chain required by Phase 3.6 and later migrations.
"""
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    with op.batch_alter_table("servers", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("last_sync_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_sync_success_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_sync_failure_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("response_time_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("health_reason", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("consecutive_successes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("stale_data", sa.Boolean(), nullable=False, server_default=sa.true()))

def downgrade() -> None:
    with op.batch_alter_table("servers", recreate="always") as batch_op:
        for name in ("stale_data", "consecutive_successes", "consecutive_failures", "health_reason", "response_time_ms", "last_sync_failure_at", "last_sync_success_at", "last_sync_attempt_at"):
            batch_op.drop_column(name)
