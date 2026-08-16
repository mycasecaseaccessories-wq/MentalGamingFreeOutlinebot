from alembic import op
import sqlalchemy as sa
revision='0015'; down_revision='0014'; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('server_capacity_reservations',sa.Column('id',sa.Integer(),primary_key=True,autoincrement=True),sa.Column('public_reservation_id',sa.String(48),nullable=False),sa.Column('server_id',sa.Integer(),sa.ForeignKey('servers.id',ondelete='RESTRICT'),nullable=False),sa.Column('workload_type',sa.String(32),nullable=False),sa.Column('owner_reference',sa.String(160),nullable=False),sa.Column('status',sa.String(24),nullable=False,server_default='pending'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('committed_at',sa.DateTime(timezone=True)),sa.Column('released_at',sa.DateTime(timezone=True)),sa.UniqueConstraint('public_reservation_id',name='uq_reservation_public_id'),sa.UniqueConstraint('owner_reference',name='uq_reservation_owner_reference'))
 op.create_index('ix_server_capacity_reservations_public_reservation_id','server_capacity_reservations',['public_reservation_id'])
 op.create_index('ix_server_capacity_reservations_server_id','server_capacity_reservations',['server_id'])
 op.create_index('ix_server_capacity_reservations_status','server_capacity_reservations',['status'])
 op.create_index('ix_server_capacity_reservations_expires_at','server_capacity_reservations',['expires_at'])
def downgrade(): op.drop_table('server_capacity_reservations')
