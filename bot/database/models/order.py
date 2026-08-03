"""
OrderORM — purchase orders linking users to packages.

An order is created when a user initiates a package purchase.
It transitions through statuses: pending → paid → fulfilled → cancelled.

Columns
-------
user_id      FK → users.id.
package_id   FK → packages.id — snapshot of the purchased package.
vpn_key_id   FK → vpn_keys.id — set once the key is issued (nullable until then).
amount       Amount charged in the package currency at the time of purchase.
currency     ISO 4217 code matching the package price at purchase time.
status       Order lifecycle state (see STATUS_* constants below).
payment_ref  External payment gateway reference / transaction ID.
notes        Admin notes for manual adjustments.
"""

from __future__ import annotations

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class OrderORM(BaseModel):
    """
    VPN subscription purchase order.

    Phase 0.2: schema placeholder.
    Phase 3:   payment gateway integration writes payment_ref.
    Phase 4:   VPNService sets vpn_key_id on fulfilment.

    Status values
    -------------
    pending     Order created, awaiting payment.
    paid        Payment confirmed, key provisioning queued.
    fulfilled   Key issued and delivered to the user.
    cancelled   Order cancelled before fulfilment.
    refunded    Payment refunded (admin action).
    """

    __tablename__ = "orders"

    # Status constants — use these instead of bare strings.
    STATUS_PENDING   = "pending"
    STATUS_PAID      = "paid"
    STATUS_FULFILLED = "fulfilled"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED  = "refunded"

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="FK → users.id",
    )
    package_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="FK → packages.id — package chosen at order time",
    )
    vpn_key_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="FK → vpn_keys.id — set after the key is provisioned",
    )
    amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Amount charged in the order currency",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="ISO 4217 currency code at time of purchase",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_PENDING,
        index=True,
        comment="Order lifecycle state",
    )
    payment_ref: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="External payment gateway transaction ID",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin-only notes for manual adjustments",
    )
