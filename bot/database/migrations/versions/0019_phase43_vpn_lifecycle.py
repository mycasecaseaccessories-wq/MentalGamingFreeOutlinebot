"""Phase 4.3 VPN key duration and lifecycle state."""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vpn_keys") as batch_op:
        batch_op.add_column(sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("lifecycle_cleanup_status", sa.String(length=24), nullable=False, server_default="not_required"))
        batch_op.add_column(sa.Column("lifecycle_cleanup_attempts", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("lifecycle_cleanup_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("lifecycle_cleanup_error", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("lifecycle_reason", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("lifecycle_note", sa.String(length=256), nullable=True))
        batch_op.create_index("ix_vpn_keys_expires_at", ["expires_at"], unique=False)
        batch_op.create_index("ix_vpn_keys_lifecycle_cleanup_status", ["lifecycle_cleanup_status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("vpn_keys") as batch_op:
        batch_op.drop_index("ix_vpn_keys_lifecycle_cleanup_status")
        batch_op.drop_index("ix_vpn_keys_expires_at")
        for name in ("lifecycle_note", "lifecycle_reason", "lifecycle_cleanup_error", "lifecycle_cleanup_at", "lifecycle_cleanup_attempts", "lifecycle_cleanup_status", "activated_at"):
            batch_op.drop_column(name)
