"""Phase 3.1 server domain and safe manual-registration state.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("servers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("public_server_id", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("display_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("host", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("provider_type", sa.String(length=32), nullable=False, server_default="outline"))
        batch_op.add_column(sa.Column("integration_type", sa.String(length=32), nullable=False, server_default="manual"))
        batch_op.add_column(sa.Column("country_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("health_status", sa.String(length=32), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
        batch_op.add_column(sa.Column("weight", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("max_users", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("current_users", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("traffic_limit_bytes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("used_traffic_bytes", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("free_trial_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("paid_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("vip_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("provider_server_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("api_endpoint_reference", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("secret_reference", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))
        batch_op.alter_column("api_url", existing_type=sa.String(length=512), nullable=True)
        batch_op.alter_column("cert_sha256", existing_type=sa.String(length=64), nullable=True)
        batch_op.create_unique_constraint("uq_servers_public_server_id", ["public_server_id"])

    op.execute("UPDATE servers SET public_server_id = 'LEGACY-' || id WHERE public_server_id IS NULL")
    op.execute("UPDATE servers SET status = 'unknown', health_status = 'unknown', enabled = 0, is_active = 0 WHERE status IS NULL OR status = 'online'")
    op.create_index("ix_servers_status_enabled", "servers", ["status", "enabled"])
    op.create_index("ix_servers_region_country", "servers", ["region", "country_code"])


def downgrade() -> None:
    op.drop_index("ix_servers_region_country", table_name="servers")
    op.drop_index("ix_servers_status_enabled", table_name="servers")
    with op.batch_alter_table("servers", schema=None) as batch_op:
        batch_op.drop_constraint("uq_servers_public_server_id", type_="unique")
        for name in (
            "metadata", "archived_at", "last_sync_at", "last_health_check_at", "secret_reference",
            "api_endpoint_reference", "provider_server_id", "vip_enabled", "paid_enabled", "free_trial_enabled",
            "used_traffic_bytes", "traffic_limit_bytes", "current_users", "max_users", "weight", "priority",
            "maintenance_mode", "enabled", "health_status", "status", "country_name", "integration_type",
            "provider_type", "host", "display_name", "public_server_id",
        ):
            batch_op.drop_column(name)
        batch_op.alter_column("api_url", existing_type=sa.String(length=512), nullable=False)
        batch_op.alter_column("cert_sha256", existing_type=sa.String(length=64), nullable=False)
