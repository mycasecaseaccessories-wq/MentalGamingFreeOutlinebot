"""Phase 2.2 — wallet payment ledger linkage and idempotency protection.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("order_id", sa.Integer(), nullable=True, comment="Order primary key for purchase debits"),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
            comment="One-time key preventing duplicate wallet debits",
        ),
    )
    op.create_index("ix_transactions_order_id", "transactions", ["order_id"], unique=False)
    op.create_index(
        "uq_transactions_idempotency_key",
        "transactions",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_idempotency_key", table_name="transactions")
    op.drop_index("ix_transactions_order_id", table_name="transactions")
    op.drop_column("transactions", "idempotency_key")
    op.drop_column("transactions", "order_id")
