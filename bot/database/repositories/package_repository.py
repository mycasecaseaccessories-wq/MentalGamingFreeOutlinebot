"""
PackageRepository — data access for the packages table.

Manages the VPN subscription package catalogue.
Admins create / update packages; users read the active list.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models.package import PackageORM
from .base import BaseRepository


class PackageRepository(BaseRepository[PackageORM, PackageORM]):
    """
    Handles all database operations for the packages table.

    Phase 0.2: CRUD inherited; custom queries stubbed.
    Phase 2:   Admin panel calls create() / update() to manage the catalogue.
               PackageService.list_active() calls list_active().
    """

    orm_class    = PackageORM
    domain_class = PackageORM

    async def list_active(self) -> List[PackageORM]:
        """
        Return all active packages ordered by sort_order ascending.

        Used by the user-facing package selection menu.
        """
        stmt = (
            select(PackageORM)
            .where(PackageORM.is_active.is_(True))
            .order_by(PackageORM.sort_order, PackageORM.price)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_customer_visible(self) -> List[PackageORM]:
        """Return only published package types intended for customer purchase."""
        stmt = (
            select(PackageORM)
            .where(
                PackageORM.is_active.is_(True),
                PackageORM.visible.is_(True),
                PackageORM.status == "active",
                PackageORM.package_type.in_(("paid", "promotion", "vip")),
            )
            .order_by(PackageORM.sort_order, PackageORM.price)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_customer_visible(self, package_id: int) -> Optional[PackageORM]:
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
        """
        Soft-delete a package by setting is_active = False.

        Args:
            package_id: Primary key of the package to deactivate.

        Returns:
            Updated PackageORM, or None if not found.
        """
        return await self.update(package_id, is_active=False)
