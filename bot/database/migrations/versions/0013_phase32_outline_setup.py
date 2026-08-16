"""Phase 3.2 Outline setup credential and verification metadata.

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("servers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("credential_ciphertext", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("outline_version", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("api_compatible", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("metrics_available", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("existing_key_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("servers", schema=None) as batch_op:
        for name in ("existing_key_count", "metrics_available", "api_compatible", "outline_version", "verified_at", "credential_ciphertext"):
            batch_op.drop_column(name)
