"""Phase 2.4 — admin payment review queue and decision indexes."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_payment_submissions_status_submitted_at",
        "payment_submissions",
        ["status", "submitted_at"],
        unique=False,
    )
    op.create_index(
        "ix_payment_submissions_order_status",
        "payment_submissions",
        ["order_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_submissions_order_status", table_name="payment_submissions")
    op.drop_index("ix_payment_submissions_status_submitted_at", table_name="payment_submissions")
