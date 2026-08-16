"""Domain models for manual payment submissions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PaymentSubmission:
    id: int
    public_payment_id: str
    order_id: int
    user_id: int
    payment_method: str
    amount: Decimal
    currency: str
    status: str
    transaction_reference: str | None
    proof_file_id: str | None
    proof_file_unique_id: str | None
    proof_file_type: str | None
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class PaymentSubmissionReceipt:
    public_payment_id: str
    public_order_id: str
    status: str
    amount: Decimal
    currency: str
    payment_method: str
    submitted_at: datetime
    duplicate: bool = False
