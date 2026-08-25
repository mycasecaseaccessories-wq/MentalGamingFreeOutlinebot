"""Provider-side payment verification contracts for Phase 8.3.

Telegram callbacks and customer input are deliberately not accepted as
verification results. Concrete integrations must implement ``verify_payment``
and return an authoritative, typed result from the provider API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderVerification:
    """Authoritative fields returned by a payment provider."""

    provider: str
    provider_reference: str
    status: str
    amount: Decimal
    currency: str
    verified_at: datetime

    @property
    def is_successful(self) -> bool:
        return self.status.lower() in {"verified", "succeeded", "paid", "completed"}


@dataclass(frozen=True, slots=True)
class ProviderRefund:
    """Authoritative refund result returned by a payment provider."""

    provider: str
    provider_reference: str
    refund_reference: str
    status: str
    amount: Decimal
    currency: str
    refunded_at: datetime

    @property
    def is_successful(self) -> bool:
        return self.status.lower() in {"refunded", "succeeded", "completed"}


class PaymentProvider(Protocol):
    """Provider adapter; implementations must query the provider itself."""

    provider_name: str

    async def verify_payment(self, provider_payment_id: str) -> ProviderVerification:
        """Return provider-authoritative payment data or raise on failure."""
        ...

    async def refund_payment(
        self,
        provider_reference: str,
        *,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> ProviderRefund:
        """Request and return a provider-authoritative refund result."""
        ...
