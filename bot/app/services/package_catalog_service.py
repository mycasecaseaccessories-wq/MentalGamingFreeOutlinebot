"""Read-only, customer-safe package catalogue service."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.models.package_catalog import PackagePage, PackageSelection, PackageSummary
from app.services.base import BaseService
from database.repositories.package_repository import PackageRepository


class PackageCatalogService(BaseService):
    async def list_visible(self, *, page: int = 1, page_size: int = 10) -> PackagePage:
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        async with self.db.session() as session:
            rows = await PackageRepository(session).list_customer_visible()
        total = len(rows)
        start = (page - 1) * page_size
        items = tuple(self._summary(row) for row in rows[start:start + page_size])
        return PackagePage(
            items=items, page=page, page_size=page_size, total=total,
            has_previous=page > 1, has_next=start + page_size < total,
        )

    async def get_visible(self, package_id: int) -> PackageSummary | None:
        async with self.db.session() as session:
            row = await PackageRepository(session).get_customer_visible(package_id)
        return self._summary(row) if row else None

    async def select(self, user_id: int, package_id: int) -> PackageSelection | None:
        item = await self.get_visible(package_id)
        if item is None:
            return None
        return PackageSelection(
            user_id=user_id, package_id=item.package_id, package_name=item.name,
            quoted_price=item.price, currency=item.currency,
        )

    @staticmethod
    def _summary(row) -> PackageSummary:
        return PackageSummary(
            package_id=row.id, name=row.name, package_type=getattr(row, "package_type", "paid"),
            price=Decimal(str(row.price)), currency=row.currency,
            data_limit_gb=row.data_limit_gb, duration_days=row.duration_days,
            device_limit=getattr(row, "device_limit", None) or row.max_devices,
            priority=getattr(row, "priority", "normal"),
            server_policy=getattr(row, "server_policy", "auto"),
            country=getattr(row, "country", None), renewable=getattr(row, "renewable", True),
            description=row.description, badge=getattr(row, "badge", None),
            promo_label=getattr(row, "promo_label", None),
            display_order=row.sort_order,
        )