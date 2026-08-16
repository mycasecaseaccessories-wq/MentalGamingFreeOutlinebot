"""Phase 6.4 promo codes, coupons, and bonus entitlements.

Revision ID: 0031_phase64_promos
Revises: 0030_phase63_missions
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_phase64_promos"
down_revision = "0030_phase63_missions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_promo_id", sa.String(40), nullable=False),
        sa.Column("code_normalized", sa.String(64), nullable=False),
        sa.Column("display_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("promo_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reward_type", sa.String(32), nullable=False),
        sa.Column("reward_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("reward_expiry_seconds", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("max_redemptions_per_user", sa.Integer(), nullable=False),
        sa.Column("reserved_count", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("minimum_purchase_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("eligibility_policy", sa.JSON(), nullable=True),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("reward_policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_promo_codes_created_by", ondelete="RESTRICT"),
        sa.UniqueConstraint("public_promo_id", name="uq_promo_codes_public_promo_id"),
        sa.UniqueConstraint("code_normalized", name="uq_promo_codes_code_normalized"),
    )
    for name, cols in (("ix_promo_codes_status", ["status"]), ("ix_promo_codes_starts_at", ["starts_at"]), ("ix_promo_codes_expires_at", ["expires_at"]), ("ix_promo_codes_code_normalized", ["code_normalized"])):
        op.create_index(name, "promo_codes", cols)

    op.create_table(
        "promo_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_redemption_id", sa.String(40), nullable=False),
        sa.Column("promo_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reward_reference", sa.String(180), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("reservation_key", sa.String(96), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("eligibility_snapshot", sa.JSON(), nullable=True),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["promo_id"], ["promo_codes.id"], name="fk_promo_redemptions_promo", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_promo_redemptions_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_promo_redemptions_order", ondelete="RESTRICT"),
        sa.UniqueConstraint("public_redemption_id", name="uq_promo_redemptions_public_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_promo_redemptions_idempotency_key"),
        sa.UniqueConstraint("promo_id", "user_id", "reservation_key", name="uq_promo_redemptions_user_reservation"),
    )
    for name, cols in (("ix_promo_redemptions_promo_id", ["promo_id"]), ("ix_promo_redemptions_user_id", ["user_id"]), ("ix_promo_redemptions_status", ["status"]), ("ix_promo_redemptions_idempotency_key", ["idempotency_key"]), ("ix_promo_redemptions_order_id", ["order_id"])):
        op.create_index(name, "promo_redemptions", cols)


def downgrade():
    for name in ("ix_promo_redemptions_order_id", "ix_promo_redemptions_idempotency_key", "ix_promo_redemptions_status", "ix_promo_redemptions_user_id", "ix_promo_redemptions_promo_id"):
        op.drop_index(name, table_name="promo_redemptions")
    op.drop_table("promo_redemptions")
    for name in ("ix_promo_codes_code_normalized", "ix_promo_codes_expires_at", "ix_promo_codes_starts_at", "ix_promo_codes_status"):
        op.drop_index(name, table_name="promo_codes")
    op.drop_table("promo_codes")
