"""Domain models for customer-facing manual payment instructions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ManualPaymentMethod:
    """A configured payment destination with secrets excluded by construction."""

    method_id: str
    name: str
    currency: str
    instructions: str
    enabled: bool = True
    account_name: str | None = None
    account_number: str | None = None
    phone_number: str | None = None
    wallet_address: str | None = None
    network: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    qr_image_url: str | None = None
    display_order: int = 0

    @classmethod
    def from_config(cls, raw: dict[str, Any]) -> "ManualPaymentMethod | None":
        """Parse only public configuration fields; reject malformed identifiers."""
        method_id = str(raw.get("method_id", "")).strip().lower()
        name = str(raw.get("name", "")).strip()
        currency = str(raw.get("currency", "")).strip().upper()
        instructions = str(raw.get("instructions", "")).strip()
        if not method_id or not name or not currency or not instructions:
            return None
        try:
            minimum = raw.get("min_amount")
            maximum = raw.get("max_amount")
            return cls(
                method_id=method_id,
                name=name,
                currency=currency,
                instructions=instructions,
                enabled=bool(raw.get("enabled", False)),
                account_name=_optional_text(raw.get("account_name")),
                account_number=_optional_text(raw.get("account_number")),
                phone_number=_optional_text(raw.get("phone_number")),
                wallet_address=_optional_text(raw.get("wallet_address")),
                network=_optional_text(raw.get("network")),
                min_amount=Decimal(str(minimum)) if minimum is not None else None,
                max_amount=Decimal(str(maximum)) if maximum is not None else None,
                qr_image_url=_optional_text(raw.get("qr_image_url")),
                display_order=int(raw.get("display_order", 0)),
            )
        except (TypeError, ValueError):
            return None

    def accepts(self, amount: Decimal, currency: str) -> bool:
        """Return whether the configured method can receive this order."""
        if not self.enabled or self.currency != currency.upper():
            return False
        if self.min_amount is not None and amount < self.min_amount:
            return False
        if self.max_amount is not None and amount > self.max_amount:
            return False
        return True

    def public_fields(self) -> dict[str, Any]:
        """Return only fields safe to render to a customer."""
        return {
            "method_id": self.method_id,
            "name": self.name,
            "currency": self.currency,
            "instructions": self.instructions,
            "account_name": self.account_name,
            "account_number": self.account_number,
            "phone_number": self.phone_number,
            "wallet_address": self.wallet_address,
            "network": self.network,
            "min_amount": str(self.min_amount) if self.min_amount is not None else None,
            "max_amount": str(self.max_amount) if self.max_amount is not None else None,
            "qr_image_url": self.qr_image_url,
            "display_order": self.display_order,
        }


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
