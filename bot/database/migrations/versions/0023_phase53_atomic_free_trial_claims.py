"""Phase 5.3 atomic Free Trial claim acceptance."""
from alembic import op
import sqlalchemy as sa
revision = "0023_phase53_atomic_free_trial_claims"
down_revision = "0022_phase52_membership_targets"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_table("free_trial_entitlements", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("source", sa.String(48), nullable=False), sa.Column("remaining_uses", sa.Integer(), nullable=False, server_default="1"), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), sa.Column("data_limit_bytes", sa.Integer(), nullable=True), sa.Column("duration_seconds", sa.Integer(), nullable=True), sa.Column("device_limit", sa.Integer(), nullable=True), sa.Column("status", sa.String(24), nullable=False, server_default="active"))
    op.create_index("ix_free_trial_entitlements_user_id", "free_trial_entitlements", ["user_id"])
    with op.batch_alter_table("free_trial_claims", recreate="always") as batch_op:
        for column in [sa.Column("entitlement_id", sa.Integer(), nullable=True), sa.Column("period_start", sa.DateTime(timezone=True), nullable=True), sa.Column("source", sa.String(24), nullable=False, server_default="daily_free"), sa.Column("data_limit_bytes", sa.BigInteger(), nullable=True), sa.Column("duration_seconds", sa.Integer(), nullable=True), sa.Column("device_limit", sa.Integer(), nullable=True), sa.Column("policy_snapshot_json", sa.Text(), nullable=False, server_default="{}"), sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True), sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True), sa.Column("cancellation_reason", sa.String(96), nullable=True)]:
            batch_op.add_column(column)
        batch_op.create_foreign_key("fk_free_trial_claim_entitlement", "free_trial_entitlements", ["entitlement_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_free_trial_claims_period_start", "free_trial_claims", ["period_start"])
    op.create_index("uq_free_trial_claim_daily_period", "free_trial_claims", ["user_id", "period_start", "source"], unique=True, sqlite_where=sa.text("source = 'daily_free'"))
    op.execute("UPDATE free_trial_claims SET period_start = claimed_at WHERE period_start IS NULL")
    op.execute("UPDATE free_trial_claims SET data_limit_bytes = 0 WHERE data_limit_bytes IS NULL")
    op.execute("UPDATE free_trial_claims SET duration_seconds = 0 WHERE duration_seconds IS NULL")
    op.execute("UPDATE free_trial_claims SET accepted_at = claimed_at WHERE accepted_at IS NULL")
def downgrade() -> None:
    op.drop_index("uq_free_trial_claim_daily_period", table_name="free_trial_claims")
    op.drop_index("ix_free_trial_claims_period_start", table_name="free_trial_claims")
    with op.batch_alter_table("free_trial_claims", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_free_trial_claim_entitlement", type_="foreignkey")
        for name in ("cancellation_reason", "cancelled_at", "accepted_at", "policy_snapshot_json", "device_limit", "duration_seconds", "data_limit_bytes", "source", "period_start", "entitlement_id"):
            batch_op.drop_column(name)
    op.drop_index("ix_free_trial_entitlements_user_id", table_name="free_trial_entitlements")
    op.drop_table("free_trial_entitlements")
