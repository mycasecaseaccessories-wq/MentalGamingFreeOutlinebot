"""Phase 4.1 VPNKey provider and operation binding."""
from alembic import op
import sqlalchemy as sa
revision="0017"; down_revision="0016"; branch_labels=None; depends_on=None
def upgrade():
 with op.batch_alter_table("vpn_keys") as b:
  b.add_column(sa.Column("provider_type",sa.String(32),nullable=False,server_default="outline")); b.add_column(sa.Column("order_id",sa.Integer(),nullable=True)); b.add_column(sa.Column("provisioning_operation_id",sa.Integer(),nullable=True)); b.add_column(sa.Column("source_type",sa.String(32),nullable=False,server_default="paid_order")); b.add_column(sa.Column("provisioned_at",sa.DateTime(timezone=True),nullable=True)); b.create_foreign_key("fk_vpn_keys_order_id","orders",["order_id"],["id"],ondelete="RESTRICT"); b.create_foreign_key("fk_vpn_keys_provisioning_operation_id","vpn_provisioning_operations",["provisioning_operation_id"],["id"],ondelete="RESTRICT"); b.create_unique_constraint("uq_vpn_keys_provider_identity",["server_id","provider_type","outline_key_id"]); b.create_index("ix_vpn_keys_order_id",["order_id"]); b.create_index("ix_vpn_keys_provisioning_operation_id",["provisioning_operation_id"])
def downgrade():
 with op.batch_alter_table("vpn_keys") as b:
  b.drop_index("ix_vpn_keys_provisioning_operation_id"); b.drop_index("ix_vpn_keys_order_id"); b.drop_constraint("uq_vpn_keys_provider_identity",type_="unique"); b.drop_constraint("fk_vpn_keys_provisioning_operation_id",type_="foreignkey"); b.drop_constraint("fk_vpn_keys_order_id",type_="foreignkey")
  for n in ("provisioned_at","source_type","provisioning_operation_id","order_id","provider_type"): b.drop_column(n)
