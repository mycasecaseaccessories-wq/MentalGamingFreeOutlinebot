"""Database-only access for customer VPN key history."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import case, func, select

from database.models.vpn_key import VPNKeyORM
from .base import BaseRepository


_STATUS_ORDER = case(
    (VPNKeyORM.status == "active", 0),
    (VPNKeyORM.status == "renewing", 1),
    (VPNKeyORM.status == "pending", 2),
    (VPNKeyORM.status == "suspended", 3),
    (VPNKeyORM.status == "expired", 4),
    (VPNKeyORM.status == "revoked", 5),
    else_=6,
)


class VPNKeyRepository(BaseRepository[VPNKeyORM, VPNKeyORM]):
    """Read/write repository for VPN keys; Phase 1.5 uses read methods only."""

    orm_class = VPNKeyORM
    domain_class = VPNKeyORM

    async def get_active_keys_for_user(self, user_id: int) -> List[VPNKeyORM]:
        stmt = select(VPNKeyORM).where(
            VPNKeyORM.user_id == user_id,
            VPNKeyORM.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user(
        self,
        user_id: int,
        *,
        limit: int = 5,
        offset: int = 0,
    ) -> List[VPNKeyORM]:
        """Return all historical keys for a user, ordered for customer usefulness."""
        stmt = (
            select(VPNKeyORM)
            .where(VPNKeyORM.user_id == user_id)
            .order_by(
                _STATUS_ORDER.asc(),
                VPNKeyORM.expires_at.desc().nullslast(),
                VPNKeyORM.created_at.desc(),
                VPNKeyORM.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(VPNKeyORM)
            .where(VPNKeyORM.user_id == user_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_owned(self, key_id: int, user_id: int) -> Optional[VPNKeyORM]:
        """Return key only when it belongs to user_id (IDOR-safe lookup)."""
        stmt = select(VPNKeyORM).where(
            VPNKeyORM.id == key_id,
            VPNKeyORM.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_expiring_keys(self, before: datetime) -> List[VPNKeyORM]:
        stmt = select(VPNKeyORM).where(
            VPNKeyORM.is_active.is_(True),
            VPNKeyORM.expires_at.is_not(None),
            VPNKeyORM.expires_at <= before,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke(self, key_id: int) -> Optional[VPNKeyORM]:
        """Legacy Phase 4 helper; not called by Phase 1.5 UI."""
        return await self.update(key_id, is_active=False, status="revoked")

    async def get_by_outline_key_id(
        self,
        server_id: int,
        outline_key_id: int,
    ) -> Optional[VPNKeyORM]:
        stmt = select(VPNKeyORM).where(
            VPNKeyORM.server_id == server_id,
            VPNKeyORM.outline_key_id == outline_key_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
