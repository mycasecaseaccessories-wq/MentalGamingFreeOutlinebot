"""Phase 1.1: explicit language selection state."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.add_column(sa.Column("language_selected", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.drop_column("language_selected")