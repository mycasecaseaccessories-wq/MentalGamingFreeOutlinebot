"""Phase 6.5 referral analytics and anti-abuse observations.

Revision ID: 0032_phase65_referral_analytics
Revises: 0031_phase64_promos
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0032_phase65_referral_analytics"
down_revision = "0031_phase64_promos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("referral_reward_blocked", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("referral_reward_block_reason", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("referral_reward_blocked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("referral_reward_blocked_by", sa.BigInteger(), nullable=True))
    op.execute("UPDATE users SET referral_reward_blocked = 0 WHERE referral_reward_blocked IS NULL")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("referral_reward_blocked", existing_type=sa.Boolean(), nullable=False)

    op.create_table(
        "referral_risk_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_observation_id", sa.String(length=48), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("referral_id", sa.Integer(), nullable=True),
        sa.Column("reward_id", sa.Integer(), nullable=True),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("action", sa.String(length=32), nullable=False, server_default="observe"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("policy_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["referral_id"], ["referrals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reward_id"], ["referral_rewards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("public_observation_id", name="uq_referral_risk_observation_public"),
        sa.UniqueConstraint("dedupe_key", name="uq_referral_risk_observation_dedupe"),
    )
    for column in ("user_id", "referral_id", "reward_id", "signal_type", "risk_level", "action", "status", "observed_at"):
        op.create_index(f"ix_referral_risk_observations_{column}", "referral_risk_observations", [column])


def downgrade() -> None:
    for column in ("user_id", "referral_id", "reward_id", "signal_type", "risk_level", "action", "status", "observed_at"):
        op.drop_index(f"ix_referral_risk_observations_{column}", table_name="referral_risk_observations")
    op.drop_table("referral_risk_observations")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("referral_reward_blocked_by")
        batch.drop_column("referral_reward_blocked_at")
        batch.drop_column("referral_reward_block_reason")
        batch.drop_column("referral_reward_blocked")
