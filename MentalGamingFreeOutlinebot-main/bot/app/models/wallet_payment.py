"""Domain objects for Phase 2.2 wallet-payment preview and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class WalletPaymentPreview:
    """Read-only confirmation data; constructing this never mutates state."""

    public_order_id: str
    package_name: str
    amount: Decimal
    currency: str
    wallet_balance: Decimal
    balance_after: Decimal
    expires_at: datetime | None


@dataclass(frozen=True)
class WalletPaymentReceipt:
    """Committed payment result returned after the DB transaction succeeds."""

    public_order_id: str
    transaction_id: int
    payment_reference: str
    amount: Decimal
    currency: str
    remaining_balance: Decimal
    paid_at: datetime
    already_processed: bool = False
