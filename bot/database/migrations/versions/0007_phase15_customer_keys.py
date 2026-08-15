"""Phase 1.5: customer VPN key read-model fields."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vpn_keys") as batch_op:
        batch_op.add_column(sa.Column("used_bytes", sa.BigInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("device_limit", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("package_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("key_type", sa.String(32), nullable=False, server_default="paid"))
        batch_op.add_column(sa.Column("status", sa.String(32), nullable=False, server_default="active"))
        batch_op.add_column(sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_vpn_keys_package_id", ["package_id"], unique=False)
        batch_op.create_index("ix_vpn_keys_status", ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("vpn_keys") as batch_op:
        batch_op.drop_index("ix_vpn_keys_status")
        batch_op.drop_index("ix_vpn_keys_package_id")
        for name in ("last_synced_at", "status", "key_type", "package_id", "device_limit", "used_bytes"):
            batch_op.drop_column(name)