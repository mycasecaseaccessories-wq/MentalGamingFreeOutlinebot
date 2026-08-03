"""
VPNKeyRepository — data access for the vpn_keys table.

Manages the lifecycle of Outline access keys: issuance, revocation,
expiry queries, and per-user key history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select

from database.models.vpn_key import VPNKeyORM
from .base import BaseRepository


class VPNKeyRepository(BaseRepository[VPNKeyORM, VPNKeyORM]):
    """
    Handles all database operations for the vpn_keys table.

    Phase 0.2: CRUD inherited; lifecycle queries stubbed.
    Phase 4:   VPNService uses these to track issued and revoked keys.
    """

    orm_class    = VPNKeyORM
    domain_class = VPNKeyORM

    async def get_active_keys_for_user(self, user_id: int) -> List[VPNKeyORM]:
        """Return all active (non-revoked) keys owned by the given user."""
        stmt = (
            select(VPNKeyORM)
            .where(VPNKeyORM.user_id == user_id, VPNKeyORM.is_active.is_(True))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_expiring_keys(self, before: datetime) -> List[VPNKeyORM]:
        """
        Return active keys whose expires_at is before the given UTC datetime.

        Used by the scheduler to auto-revoke expired keys.

        Args:
            before: UTC cutoff timestamp — keys expiring before this are returned.
        """
        stmt = (
            select(VPNKeyORM)
            .where(
                VPNKeyORM.is_active.is_(True),
                VPNKeyORM.expires_at.is_not(None),
                VPNKeyORM.expires_at <= before,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke(self, key_id: int) -> Optional[VPNKeyORM]:
        """Mark a key as revoked (is_active = False)."""
        return await self.update(key_id, is_active=False)

    async def get_by_outline_key_id(
        self, server_id: int, outline_key_id: int
    ) -> Optional[VPNKeyORM]:
        """
        Look up a key by its server-scoped Outline key ID.

        The combination (server_id, outline_key_id) is unique.
        """
        stmt = select(VPNKeyORM).where(
            VPNKeyORM.server_id == server_id,
            VPNKeyORM.outline_key_id == outline_key_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
