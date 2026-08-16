"""Read-only customer package catalogue service for Phase 1.4."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import secrets

from app.models.package_catalog import PackagePage, PackageSelection, PackageSummary
from database.repositories.package_repository import PackageRepository
from .base import BaseService


class PackageCatalogService(BaseService):
    """Customer-facing package catalogue. No payments or VPN provisioning."""

    @staticmethod
    def _summary(row) -> PackageSummary:
        return PackageSummary(
            package_id=row.id,
            name=row.name,
            package_type=row.package_type,
            price=Decimal(str(row.price)),
            currency=(row.currency or "MMK").upper(),
            data_limit_gb=None if row.data_limit_gb is None else Decimal(str(row.data_limit_gb)),
            duration_days=int(row.duration_days),
            device_limit=row.max_devices,
            priority=row.priority,
            server_policy=row.server_policy,
            country=row.country,
            renewable=bool(row.renewable),
            description=row.description,
            badge=row.badge,
            promo_label=row.promo_label,
            display_order=int(row.sort_order),
        )

    async def get_available_packages(self, *, page: int = 1, page_size: int = 6) -> PackagePage:
        page = max(1, int(page))
        page_size = min(10, max(1, int(page_size)))
        async with self.db.session() as session:
            repo = PackageRepository(session)
            total = await repo.count_customer_packages()
            rows = await repo.list_customer_packages(
                limit=page_size,
                offset=(page - 1) * page_size,
            )
        return PackagePage(
            items=tuple(self._summary(row) for row in rows),
            page=page,
            page_size=page_size,
            total=total,
            has_previous=page > 1,
            has_next=page * page_size < total,
        )

    async def get_package_details(self, package_id: int) -> PackageSummary | None:
        if package_id <= 0:
            return None
        async with self.db.session() as session:
            row = await PackageRepository(session).get_customer_package(package_id)
        return None if row is None else self._summary(row)

    async def prepare_purchase_handoff(self, user_id: int, package_id: int) -> PackageSelection | None:
        """Revalidate package and create a price snapshot only; no order/payment."""
        package = await self.get_package_details(package_id)
        if package is None:
            return None
        selected_at = datetime.now(timezone.utc)
        timeout_minutes = max(
            1, int(os.getenv("CHECKOUT_SESSION_TIMEOUT_MINUTES", "15"))
        )
        return PackageSelection(
            user_id=user_id,
            package_id=package.package_id,
            package_name=package.name,
            package_type=package.package_type,
            quoted_price=package.price,
            currency=package.currency,
            data_limit_gb=package.data_limit_gb,
            duration_days=package.duration_days,
            device_limit=package.device_limit,
            server_policy=package.server_policy,
            country=package.country,
            selected_at=selected_at,
            expires_at=selected_at + timedelta(minutes=timeout_minutes),
            checkout_token=secrets.token_urlsafe(18),
        )
