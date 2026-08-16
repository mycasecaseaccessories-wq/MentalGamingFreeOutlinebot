"""Phase 5.1 admin-managed Free Trial claims."""
from alembic import op
import sqlalchemy as sa
revision='0021_phase51_free_trial_claims'; down_revision='0020_phase46_recovery_rotation'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('free_trial_claims',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),nullable=False),sa.Column('package_id',sa.Integer(),nullable=False),sa.Column('order_id',sa.Integer(),nullable=True),sa.Column('idempotency_key',sa.String(96),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('claimed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('status',sa.String(24),nullable=False,server_default='accepted'),sa.UniqueConstraint('idempotency_key',name='uq_free_trial_claim_idempotency'))
def downgrade(): op.drop_table('free_trial_claims')
