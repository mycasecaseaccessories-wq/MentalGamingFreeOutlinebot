"""Phase 2.3 — manual payment submission and proof metadata.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_submissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_payment_id", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("transaction_reference", sa.String(length=256), nullable=True),
        sa.Column("proof_file_id", sa.String(length=256), nullable=True),
        sa.Column("proof_file_unique_id", sa.String(length=256), nullable=True),
        sa.Column("proof_file_type", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_payment_id", name="uq_payment_submissions_public_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_submissions_idempotency"),
    )
    op.create_index(
        "ix_payment_submissions_order_id",
        "payment_submissions",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_submissions_user_id",
        "payment_submissions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_submissions_status",
        "payment_submissions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_submissions_status", table_name="payment_submissions")
    op.drop_index("ix_payment_submissions_user_id", table_name="payment_submissions")
    op.drop_index("ix_payment_submissions_order_id", table_name="payment_submissions")
    op.drop_table("payment_submissions")
