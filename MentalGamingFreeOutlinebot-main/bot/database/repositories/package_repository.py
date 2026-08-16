"""Package catalogue data access."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select

from database.models.package import PackageORM
from .base import BaseRepository


class PackageRepository(BaseRepository[PackageORM, PackageORM]):
    """Database-only access for VPN packages."""

    orm_class = PackageORM
    domain_class = PackageORM

    async def list_active(self) -> List[PackageORM]:
        """Backward-compatible active list."""
        stmt = (
            select(PackageORM)
            .where(PackageORM.is_active.is_(True))
            .order_by(PackageORM.sort_order.asc(), PackageORM.price.asc(), PackageORM.name.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_customer_packages(
        self,
        *,
        limit: int = 6,
        offset: int = 0,
    ) -> List[PackageORM]:
        """Return customer-visible purchasable packages."""
        stmt = (
            select(PackageORM)
            .where(
                PackageORM.is_active.is_(True),
                PackageORM.visible.is_(True),
                PackageORM.status == "active",
                PackageORM.package_type.in_(("paid", "promotion", "vip")),
            )
            .order_by(PackageORM.sort_order.asc(), PackageORM.price.asc(), PackageORM.name.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_customer_packages(self) -> int:
        stmt = (
            select(func.count())
            .select_from(PackageORM)
            .where(
                PackageORM.is_active.is_(True),
                PackageORM.visible.is_(True),
                PackageORM.status == "active",
                PackageORM.package_type.in_(("paid", "promotion", "vip")),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_customer_package(self, package_id: int) -> Optional[PackageORM]:
        stmt = select(PackageORM).where(
            PackageORM.id == package_id,
            PackageORM.is_active.is_(True),
            PackageORM.visible.is_(True),
            PackageORM.status == "active",
            PackageORM.package_type.in_(("paid", "promotion", "vip")),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate(self, package_id: int) -> Optional[PackageORM]:
        return await self.update(package_id, is_active=False, status="disabled")
