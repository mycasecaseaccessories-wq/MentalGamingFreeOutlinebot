"""Order domain models and DTOs for Phase 2.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.enums import OrderStatus, PaymentMethod


@dataclass(frozen=True)
class OrderPackageSnapshot:
    """Immutable snapshot of the package attributes at the time of purchase."""
    package_id: int
    name: str
    package_type: str
    price: Decimal
    currency: str
    data_limit_gb: Optional[Decimal]
    duration_days: int
    device_limit: Optional[int]
    server_policy: str
    country: Optional[str]


@dataclass(frozen=True)
class Order:
    """
    Customer-safe order domain model.

    Does not expose internal database IDs, credentials, or admin metadata.
    """
    public_order_id: str
    user_id: int
    status: OrderStatus
    payment_status: str
    payment_method: Optional[PaymentMethod]
    total_amount: Decimal
    currency: str
    package_snapshot: OrderPackageSnapshot
    created_at: datetime
    expires_at: Optional[datetime]
    cancelled_at: Optional[datetime]

    @property
    def is_cancellable(self) -> bool:
        """Return True if the customer is allowed to cancel this order."""
        return self.status in (OrderStatus.PENDING, OrderStatus.WAITING_PAYMENT)

    @property
    def is_expired(self) -> bool:
        """Return True if the order has passed its expiration deadline."""
        if self.expires_at is None:
            return False
        return datetime.now(self.expires_at.tzinfo) > self.expires_at
