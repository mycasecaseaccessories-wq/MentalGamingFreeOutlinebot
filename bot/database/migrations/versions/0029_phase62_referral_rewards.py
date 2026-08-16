"""Phase 6.2 referral qualification, anti-abuse, and rewards."""
from alembic import op
import sqlalchemy as sa

revision = "0029_phase62_referral_rewards"
down_revision = "0028_phase61_referral_core"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch:
        batch.add_column(sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET first_seen_at = created_at WHERE first_seen_at IS NULL")
    with op.batch_alter_table("users", schema=None) as batch:
        batch.alter_column("first_seen_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_index("ix_users_first_seen_at", "users", ["first_seen_at"])

    with op.batch_alter_table("referrals", schema=None) as batch:
        batch.add_column(sa.Column("qualification_state", sa.String(40), nullable=True))
        batch.add_column(sa.Column("qualification_reason", sa.String(96), nullable=True))
        batch.add_column(sa.Column("risk_result", sa.String(64), nullable=True))
        batch.add_column(sa.Column("review_required", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("review_note", sa.String(256), nullable=True))
    op.execute("UPDATE referrals SET qualification_state = status WHERE qualification_state IS NULL")
    op.execute("UPDATE referrals SET review_required = 0 WHERE review_required IS NULL")
    with op.batch_alter_table("referrals", schema=None) as batch:
        batch.alter_column("qualification_state", existing_type=sa.String(40), nullable=False)
        batch.alter_column("review_required", existing_type=sa.Boolean(), nullable=False)
    op.create_index("ix_referrals_qualification_state", "referrals", ["qualification_state"])

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_reward_id", sa.String(48), nullable=False),
        sa.Column("referral_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_user_id", sa.Integer(), nullable=False),
        sa.Column("beneficiary_type", sa.String(24), nullable=False),
        sa.Column("reward_type", sa.String(32), nullable=False),
        sa.Column("reward_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("reward_cycle", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("limit_result", sa.String(64), nullable=True),
        sa.Column("risk_result", sa.String(64), nullable=True),
        sa.Column("failure_reason", sa.String(128), nullable=True),
        sa.Column("wallet_transaction_id", sa.Integer(), nullable=True),
        sa.Column("entitlement_id", sa.Integer(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["referral_id"], ["referrals.id"], name="fk_referral_reward_referral", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["beneficiary_user_id"], ["users.id"], name="fk_referral_reward_beneficiary", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name="fk_referral_reward_reviewer", ondelete="RESTRICT"),
        sa.UniqueConstraint("public_reward_id", name="uq_referral_rewards_public_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_referral_rewards_idempotency"),
        sa.UniqueConstraint("referral_id", "beneficiary_type", "reward_cycle", name="uq_referral_reward_cycle_beneficiary"),
    )
    op.create_index("ix_referral_rewards_referral_id", "referral_rewards", ["referral_id"])
    op.create_index("ix_referral_rewards_beneficiary_user_id", "referral_rewards", ["beneficiary_user_id"])
    op.create_index("ix_referral_rewards_status", "referral_rewards", ["status"])
    op.create_index("ix_referral_rewards_idempotency_key", "referral_rewards", ["idempotency_key"])

    op.create_table(
        "referral_risk_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("referral_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("risk_result", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["referral_id"], ["referrals.id"], name="fk_referral_risk_referral", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_referral_risk_actor", ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key", name="uq_referral_risk_event_idempotency"),
    )
    op.create_index("ix_referral_risk_events_referral_id", "referral_risk_events", ["referral_id"])
    op.create_index("ix_referral_risk_events_actor_user_id", "referral_risk_events", ["actor_user_id"])
    op.create_index("ix_referral_risk_events_event_type", "referral_risk_events", ["event_type"])
    op.create_index("ix_referral_risk_events_occurred_at", "referral_risk_events", ["occurred_at"])


def downgrade():
    op.drop_index("ix_referral_risk_events_occurred_at", table_name="referral_risk_events")
    op.drop_index("ix_referral_risk_events_event_type", table_name="referral_risk_events")
    op.drop_index("ix_referral_risk_events_actor_user_id", table_name="referral_risk_events")
    op.drop_index("ix_referral_risk_events_referral_id", table_name="referral_risk_events")
    op.drop_table("referral_risk_events")
    op.drop_index("ix_referral_rewards_idempotency_key", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_status", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_beneficiary_user_id", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_referral_id", table_name="referral_rewards")
    op.drop_table("referral_rewards")
    op.drop_index("ix_referrals_qualification_state", table_name="referrals")
    with op.batch_alter_table("referrals", schema=None) as batch:
        for column in ("review_note", "review_required", "risk_result", "qualification_reason", "qualification_state"):
            batch.drop_column(column)
    op.drop_index("ix_users_first_seen_at", table_name="users")
    with op.batch_alter_table("users", schema=None) as batch:
        batch.drop_column("first_seen_at")
