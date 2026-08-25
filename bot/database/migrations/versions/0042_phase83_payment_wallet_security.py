"""Phase 8.3 provider-scoped settlement references.

Revision ID: 0042_phase83_payment_wallet_security
Revises: 0041_phase82_callback_security
"""

import sqlalchemy as sa
from alembic import op

revision = "0042_phase83_payment_wallet_security"
down_revision = "0041_phase82_callback_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("provider", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payment_submissions",
        sa.Column("provider", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payment_submissions",
        sa.Column("provider_reference", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("provider_reference", sa.String(length=256), nullable=True),
    )
    op.create_index("ix_transactions_provider", "transactions", ["provider"], unique=False)
    op.create_index(
        "ix_payment_submissions_provider",
        "payment_submissions",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_payment_submissions_provider_reference",
        "payment_submissions",
        ["provider_reference"],
        unique=False,
    )
    op.create_index(
        "uq_payment_submissions_provider_reference",
        "payment_submissions",
        ["provider", "provider_reference"],
        unique=True,
    )
    op.create_index(
        "ix_transactions_provider_reference",
        "transactions",
        ["provider_reference"],
        unique=False,
    )
    # A unique index is portable across SQLite and PostgreSQL and allows
    # legacy rows with NULL provider fields while protecting real references.
    op.create_index(
        "uq_transactions_provider_reference",
        "transactions",
        ["provider", "provider_reference"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_provider_reference", table_name="transactions")
    op.drop_index("uq_payment_submissions_provider_reference", table_name="payment_submissions")
    op.drop_index("ix_payment_submissions_provider_reference", table_name="payment_submissions")
    op.drop_index("ix_payment_submissions_provider", table_name="payment_submissions")
    op.drop_index("ix_transactions_provider_reference", table_name="transactions")
    op.drop_index("ix_transactions_provider", table_name="transactions")
    op.drop_column("payment_submissions", "provider_reference")
    op.drop_column("payment_submissions", "provider")
    op.drop_column("transactions", "provider_reference")
    op.drop_column("transactions", "provider")
