"""
ServerRepository — data access for the servers table.

Manages the fleet of registered Outline VPN servers.
ServerService uses this to select servers for key issuance.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models.server import ServerORM
from .base import BaseRepository


class ServerRepository(BaseRepository[ServerORM, ServerORM]):
    """
    Handles all database operations for the servers table.

    Phase 0.2: CRUD inherited; custom queries stubbed.
    Phase 4:   ServerService uses list_active() for load-balanced key issuance.
    """

    orm_class    = ServerORM
    domain_class = ServerORM

    async def list_active(self) -> List[ServerORM]:
        """Return all active servers available for key issuance."""
        stmt = select(ServerORM).where(ServerORM.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_api_url(self, api_url: str) -> Optional[ServerORM]:
        """
        Fetch a server by its Outline management API URL.

        Used to prevent duplicate server registration.
        """
        stmt = select(ServerORM).where(ServerORM.api_url == api_url)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate(self, server_id: int) -> Optional[ServerORM]:
        """Mark a server as inactive (prevents new key issuance)."""
        return await self.update(server_id, is_active=False)
