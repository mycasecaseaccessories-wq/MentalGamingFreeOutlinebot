"""Phase 4.6 rotation and recovery state.

Revision ID: 0020_phase46_recovery_rotation
Revises: 0019_phase43_vpn_lifecycle
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_phase46_recovery_rotation"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vpn_keys", sa.Column("rotation_operation_id", sa.String(length=96), nullable=True))
    op.add_column("vpn_keys", sa.Column("recovery_status", sa.String(length=32), nullable=False, server_default="not_required"))
    op.add_column("vpn_keys", sa.Column("recovery_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vpn_keys", sa.Column("recovery_error", sa.String(length=128), nullable=True))
    op.add_column("vpn_keys", sa.Column("replaced_key_id", sa.Integer(), nullable=True))
    op.add_column("vpn_keys", sa.Column("replaces_key_id", sa.Integer(), nullable=True))
    op.create_index("ix_vpn_keys_rotation_operation_id", "vpn_keys", ["rotation_operation_id"])
    op.create_index("ix_vpn_keys_recovery_status", "vpn_keys", ["recovery_status"])


def downgrade() -> None:
    op.drop_index("ix_vpn_keys_recovery_status", table_name="vpn_keys")
    op.drop_index("ix_vpn_keys_rotation_operation_id", table_name="vpn_keys")
    op.drop_column("vpn_keys", "replaces_key_id")
    op.drop_column("vpn_keys", "replaced_key_id")
    op.drop_column("vpn_keys", "recovery_error")
    op.drop_column("vpn_keys", "recovery_attempts")
    op.drop_column("vpn_keys", "recovery_status")
    op.drop_column("vpn_keys", "rotation_operation_id")
