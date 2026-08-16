"""Admin-facing payment review DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PaymentReviewItem:
    public_payment_id: str
    public_order_id: str
    user_id: int
    telegram_id: int
    username: str | None
    customer_name: str
    payment_method: str
    amount: Decimal
    currency: str
    transaction_reference: str | None
    proof_file_id: str | None
    proof_file_unique_id: str | None
    proof_file_type: str | None
    status: str
    submitted_at: datetime
    order_status: str
    order_payment_status: str


@dataclass(frozen=True, slots=True)
class PaymentReviewPage:
    items: list[PaymentReviewItem]
    page: int
    page_size: int
    total: int
    has_previous: bool
    has_next: bool


@dataclass(frozen=True, slots=True)
class PaymentReviewDecision:
    public_payment_id: str
    public_order_id: str
    decision: str
    status: str
    already_decided: bool = False
    reason: str | None = None
