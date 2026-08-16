"""Phase 4.2 remote data-limit and usage-sync state."""
from alembic import op
import sqlalchemy as sa
revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("vpn_keys") as b:
        b.add_column(sa.Column("remote_limit_bytes", sa.BigInteger(), nullable=True))
        b.add_column(sa.Column("usage_baseline_bytes", sa.BigInteger(), nullable=False, server_default="0"))
        b.add_column(sa.Column("last_usage_sync_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("limit_source", sa.String(48), nullable=True))
        b.add_column(sa.Column("limit_source_reference", sa.String(160), nullable=True))
        b.add_column(sa.Column("limit_status", sa.String(24), nullable=False, server_default="not_applied"))
        b.add_column(sa.Column("provider_limit_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("limit_applied_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("limit_operation_id", sa.String(96), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("vpn_keys") as b:
        for name in ("limit_operation_id", "limit_applied_at", "provider_limit_verified", "limit_status", "limit_source_reference", "limit_source", "last_usage_sync_at", "usage_baseline_bytes", "remote_limit_bytes"):
            b.drop_column(name)
