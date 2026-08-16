"""Configurable manual payment method service for Phase 2.3."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.manual_payment import ManualPaymentMethod
from config.defaults import SettingKeys
from .base import BaseService
from .settings_service import SettingsService


class ManualPaymentService(BaseService):
    """Loads customer-safe manual payment destinations from SettingsService."""

    def __init__(
        self,
        db=None,
        *,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__(db)
        self.settings_service = settings_service or SettingsService(db)

    async def list_enabled_methods(
        self,
        *,
        amount: Decimal | None = None,
        currency: str | None = None,
    ) -> list[ManualPaymentMethod]:
        raw_methods = await self.settings_service.get(
            SettingKeys.MANUAL_PAYMENT_METHODS,
            default=[],
        )
        if not isinstance(raw_methods, list):
            return []
        methods = [
            parsed
            for raw in raw_methods
            if isinstance(raw, dict)
            for parsed in [ManualPaymentMethod.from_config(raw)]
            if parsed is not None and parsed.enabled
        ]
        methods.sort(key=lambda method: (method.display_order, method.method_id))
        if currency is not None:
            methods = [method for method in methods if method.currency == currency.upper()]
        if amount is not None:
            methods = [method for method in methods if method.accepts(amount, method.currency)]
        return methods

    async def get_method(
        self,
        method_id: str,
        *,
        amount: Decimal | None = None,
        currency: str | None = None,
    ) -> ManualPaymentMethod | None:
        methods = await self.list_enabled_methods(amount=amount, currency=currency)
        normalized = method_id.strip().lower()
        return next((method for method in methods if method.method_id == normalized), None)

    async def set_methods(self, methods: list[dict[str, Any]]) -> None:
        """Persist public method configuration through the typed settings layer."""
        await self.settings_service.set(
            SettingKeys.MANUAL_PAYMENT_METHODS,
            methods,
            type_="list",
            category="wallet",
            description="Enabled customer-facing manual payment destinations.",
            is_public=True,
        )
