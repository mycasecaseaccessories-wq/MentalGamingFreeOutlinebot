"""
TransactionORM — wallet debit/credit ledger.

Every change to a wallet balance is recorded as an immutable transaction.
The wallet balance is always the sum of its transactions.

Columns
-------
wallet_id   FK → wallets.id.
amount      Positive = credit, negative = debit.
currency    ISO 4217 code (should match the wallet currency).
type        Transaction type label (see TYPE_* constants).
reference   Free-text reference linking to an order, payment, or admin action.
note        Human-readable description shown to the user.
"""

from __future__ import annotations

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class TransactionORM(BaseModel):
    """
    Immutable ledger entry for wallet balance changes.

    Phase 0.2: schema placeholder.
    Phase 3:   WalletService writes entries atomically with balance updates.

    Type values
    -----------
    top_up       Funds added via payment gateway.
    purchase     Debit for a package order.
    refund       Credit issued on order refund.
    bonus        Promotional or referral bonus credit.
    adjustment   Manual admin adjustment.
    """

    __tablename__ = "transactions"

    # Type constants.
    TYPE_TOP_UP     = "top_up"
    TYPE_PURCHASE   = "purchase"
    TYPE_REFUND     = "refund"
    TYPE_BONUS      = "bonus"
    TYPE_ADJUSTMENT = "adjustment"

    wallet_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="FK → wallets.id",
    )
    order_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Order primary key for purchase debits",
    )
    amount: Mapped[float] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        comment="Credit (positive) or debit (negative) amount",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="ISO 4217 currency code",
    )
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="Transaction type label",
    )
    reference: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="External reference: order ID, payment gateway TX ID, etc.",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        unique=True,
        index=True,
        comment="One-time key preventing duplicate wallet debits",
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description shown to the user",
    )
