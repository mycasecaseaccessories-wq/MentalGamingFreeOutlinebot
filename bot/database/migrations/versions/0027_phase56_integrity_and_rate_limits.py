"""Phase 5.6 durable abuse limits and relational integrity hardening."""

from alembic import op
import sqlalchemy as sa

revision = "0027_phase56_integrity_and_rate_limits"
down_revision = "0026_phase56_paid_trial_upgrade"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("free_trial_upgrade_offers", schema=None) as batch:
        batch.create_foreign_key(
            "fk_free_trial_upgrade_offer_target_package",
            "packages",
            ["target_package_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("free_trial_upgrades", schema=None) as batch:
        batch.create_foreign_key(
            "fk_free_trial_upgrade_user", "users", ["user_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_free_trial_upgrade_vpn_key", "vpn_keys", ["vpn_key_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_free_trial_upgrade_claim", "free_trial_claims", ["claim_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_free_trial_upgrade_offer", "free_trial_upgrade_offers", ["offer_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_free_trial_upgrade_target_package",
            "packages",
            ["target_package_id_snapshot"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("free_trial_restrictions", schema=None) as batch:
        batch.create_foreign_key(
            "fk_free_trial_restriction_user", "users", ["user_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_foreign_key(
            "fk_free_trial_restriction_updated_by", "users", ["updated_by"], ["id"], ondelete="SET NULL"
        )

    op.create_table(
        "free_trial_rate_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_free_trial_rate_limit_user", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "action", name="uq_free_trial_rate_limit_user_action"),
    )
    op.create_index("ix_free_trial_rate_limits_user_id", "free_trial_rate_limits", ["user_id"])


def downgrade():
    op.drop_index("ix_free_trial_rate_limits_user_id", table_name="free_trial_rate_limits")
    op.drop_table("free_trial_rate_limits")

    with op.batch_alter_table("free_trial_restrictions", schema=None) as batch:
        batch.drop_constraint("fk_free_trial_restriction_updated_by", type_="foreignkey")
        batch.drop_constraint("fk_free_trial_restriction_user", type_="foreignkey")
    with op.batch_alter_table("free_trial_upgrades", schema=None) as batch:
        batch.drop_constraint("fk_free_trial_upgrade_target_package", type_="foreignkey")
        batch.drop_constraint("fk_free_trial_upgrade_offer", type_="foreignkey")
        batch.drop_constraint("fk_free_trial_upgrade_claim", type_="foreignkey")
        batch.drop_constraint("fk_free_trial_upgrade_vpn_key", type_="foreignkey")
        batch.drop_constraint("fk_free_trial_upgrade_user", type_="foreignkey")
    with op.batch_alter_table("free_trial_upgrade_offers", schema=None) as batch:
        batch.drop_constraint("fk_free_trial_upgrade_offer_target_package", type_="foreignkey")
