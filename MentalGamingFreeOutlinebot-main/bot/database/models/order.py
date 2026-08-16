"""Persistent order model for Phase 2.1 checkout foundation.

The model intentionally stops at order creation and payment handoff. Payment
processing, wallet mutations, and VPN provisioning belong to later phases.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class OrderORM(BaseModel):
    """VPN purchase order with immutable purchase-time package snapshots."""

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("public_order_id", name="uq_orders_public_order_id"),
        UniqueConstraint("checkout_token", name="uq_orders_checkout_token"),
    )

    STATUS_PENDING = "pending"
    STATUS_WAITING_PAYMENT = "waiting_payment"
    STATUS_AWAITING_APPROVAL = "awaiting_approval"
    STATUS_PAID = "paid"
    STATUS_COMPLETED = "completed"
    # Backward-compatible alias used by the pre-Phase-2 repository.
    STATUS_FULFILLED = STATUS_COMPLETED
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"
    STATUS_REFUNDED = "refunded"

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PENDING = "pending"
    PAYMENT_UNDER_REVIEW = "under_review"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"
    PAYMENT_CANCELLED = "cancelled"
    PAYMENT_REFUNDED = "refunded"

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Telegram user identifier for backward-compatible ownership checks",
    )
    package_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    public_order_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True,
        comment="Customer-safe, non-sequential support identifier",
    )
    checkout_token: Mapped[str | None] = mapped_column(
        String(96), nullable=True, unique=True, index=True,
        comment="Persistent idempotency key for a checkout confirmation",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_PENDING, index=True,
    )
    payment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PAYMENT_UNPAID, index=True,
    )
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"),
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Immutable package-at-purchase snapshot.
    package_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    package_type_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_limit_gb_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    duration_days_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_limit_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    server_policy_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_snapshot: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Future-compatible references; no future-phase behavior is implemented here.
    wallet_transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payment_submission_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vpn_key_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True,
    )

    # Legacy compatibility fields retained for existing code and migrations.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    payment_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    expires_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
