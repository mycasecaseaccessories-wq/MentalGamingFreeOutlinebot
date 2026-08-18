"""Server-side checkout session orchestration for Phase 2.1."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.package_catalog import PackageSelection, PackageSummary
from .base import BaseService
from .maintenance_service import MaintenanceService
from .order_service import (
    CheckoutExpiredError,
    OrderService,
    PackageChangedError,
)
from .package_catalog_service import PackageCatalogService


class CheckoutService(BaseService):
    """Validate checkout sessions without rendering Telegram UI."""

    def __init__(self, db=None, maintenance_service: MaintenanceService | None = None) -> None:
        super().__init__(db)
        self._catalog = PackageCatalogService(db=self.db)
        self._orders = OrderService(db=self.db, maintenance_service=maintenance_service)

    @staticmethod
    def _ensure_current(selection: PackageSelection, package: PackageSummary) -> None:
        if selection.expires_at <= datetime.now(timezone.utc):
            raise CheckoutExpiredError("Checkout session has expired")
        current = (
            package.package_id,
            package.name,
            package.package_type,
            package.price,
            package.currency,
            package.data_limit_gb,
            package.duration_days,
            package.device_limit,
            package.server_policy,
            package.country,
        )
        selected = (
            selection.package_id,
            selection.package_name,
            selection.package_type,
            selection.quoted_price,
            selection.currency,
            selection.data_limit_gb,
            selection.duration_days,
            selection.device_limit,
            selection.server_policy,
            selection.country,
        )
        if current != selected:
            raise PackageChangedError("Package details changed; confirmation is required again")

    async def prepare_checkout(self, selection: PackageSelection) -> PackageSelection:
        await self.validate_selection(selection)
        return selection

    async def validate_selection(self, selection: PackageSelection) -> PackageSummary:
        package = await self._catalog.get_package_details(selection.package_id)
        if package is None:
            raise PackageChangedError("Package is no longer available")
        self._ensure_current(selection, package)
        return package

    async def reload_package(self, package_id: int) -> PackageSummary | None:
        return await self._catalog.get_package_details(package_id)

    async def build_checkout_summary(self, selection: PackageSelection) -> PackageSummary:
        return await self.validate_selection(selection)

    async def create_order(self, selection: PackageSelection):
        await self.validate_selection(selection)
        return await self._orders.create_pending_order(
            selection.user_id,
            selection,
        )

    def get_checkout_session(self, selection: PackageSelection | None, user_id: int) -> PackageSelection:
        if selection is None or selection.user_id != user_id:
            raise CheckoutExpiredError("Checkout session is missing")
        if selection.expires_at <= datetime.now(timezone.utc):
            raise CheckoutExpiredError("Checkout session has expired")
        return selection

    def cancel_checkout(self, selection: PackageSelection | None, user_id: int) -> bool:
        if selection is None or selection.user_id != user_id:
            return False
        return True

    def clear_checkout_session(self, context_user_data: dict, key: str) -> None:
        context_user_data.pop(key, None)
