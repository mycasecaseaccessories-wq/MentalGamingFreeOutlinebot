"""Phase 6.1 referral tokens and attribution core."""

from alembic import op
import sqlalchemy as sa

revision = "0028_phase61_referral_core"
down_revision = "0027_phase56_integrity_and_rate_limits"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "referral_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_referral_token_user", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_referral_token_user"),
        sa.UniqueConstraint("token", name="uq_referral_token_value"),
    )
    op.create_index("ix_referral_tokens_user_id", "referral_tokens", ["user_id"])
    op.create_index("ix_referral_tokens_token", "referral_tokens", ["token"])

    with op.batch_alter_table("referrals", schema=None) as batch:
        batch.add_column(sa.Column("public_referral_id", sa.String(48), nullable=True))
        batch.add_column(sa.Column("token_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source", sa.String(32), nullable=True))
        batch.add_column(sa.Column("metadata", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("invalidation_reason", sa.String(64), nullable=True))

    op.execute("UPDATE referrals SET public_referral_id = 'REF-' || id WHERE public_referral_id IS NULL")
    op.execute("UPDATE referrals SET source = 'personal_link' WHERE source IS NULL")
    op.execute("UPDATE referrals SET status = 'pending_qualification' WHERE status = 'pending'")

    with op.batch_alter_table("referrals", schema=None) as batch:
        batch.alter_column("public_referral_id", existing_type=sa.String(48), nullable=False)
        batch.alter_column("source", existing_type=sa.String(32), nullable=False)
        batch.create_unique_constraint("uq_referrals_public_referral_id", ["public_referral_id"])
        batch.create_foreign_key("fk_referral_referrer_user", "users", ["referrer_id"], ["id"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_referral_referred_user", "users", ["referred_id"], ["id"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_referral_token", "referral_tokens", ["token_id"], ["id"], ondelete="SET NULL")

    op.create_index("ix_referrals_referred_id", "referrals", ["referred_id"], unique=True)
    op.create_index("ix_referrals_source", "referrals", ["source"])


def downgrade():
    op.drop_index("ix_referrals_source", table_name="referrals")
    op.drop_index("ix_referrals_referred_id", table_name="referrals")
    with op.batch_alter_table("referrals", schema=None) as batch:
        batch.drop_constraint("fk_referral_token", type_="foreignkey")
        batch.drop_constraint("fk_referral_referred_user", type_="foreignkey")
        batch.drop_constraint("fk_referral_referrer_user", type_="foreignkey")
        batch.drop_constraint("uq_referrals_public_referral_id", type_="unique")
        for column in ("invalidation_reason", "invalidated_at", "rewarded_at", "metadata", "source", "token_id", "public_referral_id"):
            batch.drop_column(column)
    op.drop_index("ix_referral_tokens_token", table_name="referral_tokens")
    op.drop_index("ix_referral_tokens_user_id", table_name="referral_tokens")
    op.drop_table("referral_tokens")
