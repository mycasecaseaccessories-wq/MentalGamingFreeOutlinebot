"""Phase 5.6 paid Free Trial upgrades, conversions, and restrictions."""
from alembic import op
import sqlalchemy as sa

revision = "0026_phase56_paid_trial_upgrade"
down_revision = "0025_phase55_claim_key_binding"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "free_trial_upgrade_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_offer_id", sa.String(48), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("upgrade_type", sa.String(32), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("additional_data_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("additional_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_package_id", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_purchases_per_trial", sa.Integer(), nullable=True),
        sa.UniqueConstraint("public_offer_id", name="uq_free_trial_upgrade_offer_public_id"),
    )
    op.create_index("ix_free_trial_upgrade_offers_public_offer_id", "free_trial_upgrade_offers", ["public_offer_id"])
    op.create_index("ix_free_trial_upgrade_offers_enabled", "free_trial_upgrade_offers", ["enabled"])
    op.create_table(
        "free_trial_upgrades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_upgrade_id", sa.String(48), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vpn_key_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=True),
        sa.Column("offer_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(96), nullable=False),
        sa.Column("upgrade_type", sa.String(32), nullable=False),
        sa.Column("price_snapshot", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency_snapshot", sa.String(3), nullable=False),
        sa.Column("data_bytes_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_package_id_snapshot", sa.Integer(), nullable=True),
        sa.Column("target_data_bytes", sa.Integer(), nullable=True),
        sa.Column("target_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="payment_pending"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_free_trial_upgrade_idempotency"),
        sa.UniqueConstraint("order_id", name="uq_free_trial_upgrade_order"),
    )
    op.create_index("ix_free_trial_upgrades_public_upgrade_id", "free_trial_upgrades", ["public_upgrade_id"])
    op.create_index("ix_free_trial_upgrades_user_id", "free_trial_upgrades", ["user_id"])
    op.create_index("ix_free_trial_upgrades_vpn_key_id", "free_trial_upgrades", ["vpn_key_id"])
    op.create_index("ix_free_trial_upgrades_claim_id", "free_trial_upgrades", ["claim_id"])
    op.create_index("ix_free_trial_upgrades_order_id", "free_trial_upgrades", ["order_id"])
    op.create_index("ix_free_trial_upgrades_status", "free_trial_upgrades", ["status"])
    op.create_table(
        "free_trial_restrictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_free_trial_restriction_user"),
    )
    op.create_index("ix_free_trial_restrictions_user_id", "free_trial_restrictions", ["user_id"])
    op.create_index("ix_free_trial_restrictions_blocked", "free_trial_restrictions", ["blocked"])


def downgrade():
    op.drop_index("ix_free_trial_restrictions_blocked", table_name="free_trial_restrictions")
    op.drop_index("ix_free_trial_restrictions_user_id", table_name="free_trial_restrictions")
    op.drop_table("free_trial_restrictions")
    for name in (
        "ix_free_trial_upgrades_status",
        "ix_free_trial_upgrades_order_id",
        "ix_free_trial_upgrades_claim_id",
        "ix_free_trial_upgrades_vpn_key_id",
        "ix_free_trial_upgrades_user_id",
        "ix_free_trial_upgrades_public_upgrade_id",
    ):
        op.drop_index(name, table_name="free_trial_upgrades")
    op.drop_table("free_trial_upgrades")
    op.drop_index("ix_free_trial_upgrade_offers_enabled", table_name="free_trial_upgrade_offers")
    op.drop_index("ix_free_trial_upgrade_offers_public_offer_id", table_name="free_trial_upgrade_offers")
    op.drop_table("free_trial_upgrade_offers")
