"""Phase 2.1 — order creation and checkout foundation.

Adds customer-safe identifiers, payment state, immutable package snapshots,
and expiry/idempotency fields without deleting existing order data.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("public_order_id", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("checkout_token", sa.String(96), nullable=True))
        batch_op.add_column(
            sa.Column("payment_status", sa.String(32), nullable=False, server_default="unpaid")
        )
        batch_op.add_column(sa.Column("payment_method", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("subtotal_amount", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(
            sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("total_amount", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(sa.Column("package_name_snapshot", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("package_type_snapshot", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("data_limit_gb_snapshot", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("duration_days_snapshot", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("device_limit_snapshot", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("price_snapshot", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(sa.Column("server_policy_snapshot", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("country_snapshot", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("wallet_transaction_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("payment_reference", sa.String(256), nullable=True))
        batch_op.add_column(sa.Column("payment_submission_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("approved_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch_op.create_index("ix_orders_public_order_id", ["public_order_id"], unique=True)
        batch_op.create_index("ix_orders_checkout_token", ["checkout_token"], unique=True)
        batch_op.create_index("ix_orders_expires_at", ["expires_at"], unique=False)
        batch_op.create_index("ix_orders_created_at", ["created_at"], unique=False)

    # Preserve old orders as readable orders. A legacy row is not made paid or
    # completed; it receives a deterministic support identifier and amount copy.
    op.execute(
        sa.text(
            "UPDATE orders SET "
            "public_order_id = 'LEGACY-' || CAST(id AS VARCHAR(20)), "
            "subtotal_amount = amount, total_amount = amount, price_snapshot = amount "
            "WHERE public_order_id IS NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        for index_name in (
            "ix_orders_created_at",
            "ix_orders_expires_at",
            "ix_orders_checkout_token",
            "ix_orders_public_order_id",
        ):
            batch_op.drop_index(index_name)
        for column_name in (
            "rejection_reason", "rejected_at", "approved_at", "completed_at", "paid_at",
            "cancelled_at", "expires_at", "metadata", "approved_by", "payment_submission_id",
            "payment_reference", "wallet_transaction_id", "country_snapshot",
            "server_policy_snapshot", "price_snapshot", "device_limit_snapshot",
            "duration_days_snapshot", "data_limit_gb_snapshot", "package_type_snapshot",
            "package_name_snapshot", "total_amount", "discount_amount", "subtotal_amount",
            "payment_method", "payment_status", "checkout_token", "public_order_id",
        ):
            batch_op.drop_column(column_name)
