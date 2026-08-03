"""
WalletORM — per-user wallet balances.

Each user has exactly one wallet row.  The balance reflects the sum of all
credit and debit TransactionORM entries.  Never update balance directly —
always create a Transaction and recompute.

Columns
-------
user_id     FK → users.id (unique — one wallet per user).
balance     Current balance in the default platform currency.
currency    ISO 4217 currency code for this wallet.
is_frozen   True when the wallet is locked (admin action or fraud hold).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class WalletORM(BaseModel):
    """
    User wallet holding the platform credit balance.

    Phase 0.2: schema placeholder.
    Phase 3:   WalletService uses this to debit on order placement.
    """

    __tablename__ = "wallets"

    user_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True,
        comment="FK → users.id — one wallet per user",
    )
    balance: Mapped[float] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=0.0,
        comment="Current balance — always derived from transaction ledger",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code for this wallet",
    )
    is_frozen: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True when the wallet is locked (fraud hold / admin action)",
    )
