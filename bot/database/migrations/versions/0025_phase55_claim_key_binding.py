"""Phase 5.5 bind one Free Trial claim to one VPN key."""
from alembic import op
import sqlalchemy as sa
revision='0025_phase55_claim_key_binding'; down_revision='0024_phase54_trial_server_quota'; branch_labels=None; depends_on=None
def upgrade():
    with op.batch_alter_table('free_trial_claims', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('vpn_key_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('uq_free_trial_claim_vpn_key', ['vpn_key_id'])
def downgrade():
    with op.batch_alter_table('free_trial_claims', recreate='always') as batch_op:
        batch_op.drop_constraint('uq_free_trial_claim_vpn_key', type='unique')
        batch_op.drop_column('vpn_key_id')
