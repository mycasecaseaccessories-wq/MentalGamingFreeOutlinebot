"""Phase 1.1: explicit language selection state.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.add_column(
            sa.Column(
                "language_selected",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.drop_column("language_selected")
