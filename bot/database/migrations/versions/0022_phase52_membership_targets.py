"""Phase 5.2 target-aware membership verification."""
from alembic import op
import sqlalchemy as sa
revision='0022_phase52_membership_targets'; down_revision='0021_phase51_free_trial_claims'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('membership_targets',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('target_type',sa.String(16),nullable=False),sa.Column('target_id',sa.String(128),nullable=False),sa.Column('invite_url',sa.Text(),nullable=True),sa.Column('revision',sa.Integer(),nullable=False,server_default='1'),sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column('updated_by',sa.Integer(),nullable=True),sa.UniqueConstraint('target_type','target_id',name='uq_membership_target_identity'))
    op.create_table('user_membership_verifications',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),nullable=False),sa.Column('target_id',sa.Integer(),nullable=False),sa.Column('target_revision',sa.Integer(),nullable=False),sa.Column('verified_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('user_id','target_id',name='uq_user_membership_target'))
def downgrade():
    op.drop_table('user_membership_verifications'); op.drop_table('membership_targets')
