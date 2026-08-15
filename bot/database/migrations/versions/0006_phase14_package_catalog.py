"""Phase 1.4: customer catalogue metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("packages") as batch_op:
        batch_op.add_column(sa.Column("package_type", sa.String(32), nullable=False, server_default="paid"))
        batch_op.add_column(sa.Column("status", sa.String(32), nullable=False, server_default="active"))
        batch_op.add_column(sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("renewable", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("priority", sa.String(32), nullable=False, server_default="normal"))
        batch_op.add_column(sa.Column("server_policy", sa.String(32), nullable=False, server_default="auto"))
        batch_op.add_column(sa.Column("server_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("country", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("badge", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("promo_label", sa.String(128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("packages") as batch_op:
        for name in ("promo_label", "badge", "country", "server_id", "server_policy",
                     "priority", "renewable", "visible", "status", "package_type"):
            batch_op.drop_column(name)