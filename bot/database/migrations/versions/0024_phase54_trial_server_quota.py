"""Phase 5.4 per-server Free Trial quota and claim-bound reservations."""

from alembic import op
import sqlalchemy as sa

revision = "0024_phase54_trial_server_quota"
down_revision = "0023_phase53_atomic_free_trial_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("servers", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("free_trial_daily_quota_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("free_trial_daily_quota", sa.Integer(), nullable=True))
    with op.batch_alter_table("server_capacity_reservations", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("claim_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("period_key", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key("fk_reservation_claim", "free_trial_claims", ["claim_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_unique_constraint("uq_reservation_claim_id", ["claim_id"])
    op.create_index("ix_reservation_claim_id", "server_capacity_reservations", ["claim_id"])
    op.create_index("ix_reservation_period", "server_capacity_reservations", ["server_id", "workload_type", "period_key", "status"])


def downgrade() -> None:
    op.drop_index("ix_reservation_period", table_name="server_capacity_reservations")
    op.drop_index("ix_reservation_claim_id", table_name="server_capacity_reservations")
    with op.batch_alter_table("server_capacity_reservations", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_reservation_claim_id", type_="unique")
        batch_op.drop_constraint("fk_reservation_claim", type_="foreignkey")
        batch_op.drop_column("period_key")
        batch_op.drop_column("claim_id")
    with op.batch_alter_table("servers", recreate="always") as batch_op:
        batch_op.drop_column("free_trial_daily_quota")
        batch_op.drop_column("free_trial_daily_quota_enabled")
