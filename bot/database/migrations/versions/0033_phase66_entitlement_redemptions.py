"""Phase 6.6 idempotent growth entitlement redemptions.

Revision ID: 0033_phase66_entitlement_redemptions
Revises: 0032_phase65_referral_analytics
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0033_phase66_entitlement_redemptions"
down_revision = "0032_phase65_referral_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "free_trial_entitlement_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entitlement_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="redeemed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entitlement_id"], ["free_trial_entitlements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("idempotency_key", name="uq_entitlement_redemption_idempotency"),
    )
    op.create_index("ix_free_trial_entitlement_redemptions_entitlement_id", "free_trial_entitlement_redemptions", ["entitlement_id"])
    op.create_index("ix_free_trial_entitlement_redemptions_user_id", "free_trial_entitlement_redemptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_free_trial_entitlement_redemptions_user_id", table_name="free_trial_entitlement_redemptions")
    op.drop_index("ix_free_trial_entitlement_redemptions_entitlement_id", table_name="free_trial_entitlement_redemptions")
    op.drop_table("free_trial_entitlement_redemptions")
