"""Data access for the authoritative multi-server registry."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select

from database.models.server import ServerORM
from .base import BaseRepository


class ServerRepository(BaseRepository[ServerORM, ServerORM]):
    orm_class = ServerORM
    domain_class = ServerORM

    async def list_active(self) -> list[ServerORM]:
        """Legacy allocation query; only explicitly enabled online servers qualify."""
        stmt = select(ServerORM).where(
            ServerORM.enabled.is_(True),
            ServerORM.is_active.is_(True),
            ServerORM.status == ServerORM.STATUS_ONLINE,
            ServerORM.health_status == ServerORM.HEALTH_OK,
            ServerORM.maintenance_mode.is_(False),
            ServerORM.archived_at.is_(None),
        ).order_by(ServerORM.priority, ServerORM.id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_api_url(self, api_url: str) -> Optional[ServerORM]:
        stmt = select(ServerORM).where(ServerORM.api_url == api_url)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_public_id(self, public_server_id: str) -> ServerORM | None:
        stmt = select(ServerORM).where(ServerORM.public_server_id == public_server_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_management(self, *, offset: int = 0, limit: int = 10, include_archived: bool = False) -> list[ServerORM]:
        stmt = select(ServerORM)
        if not include_archived:
            stmt = stmt.where(ServerORM.archived_at.is_(None))
        stmt = stmt.order_by(ServerORM.created_at.desc(), ServerORM.id.desc()).offset(offset).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_management(self, *, include_archived: bool = False) -> int:
        stmt = select(func.count()).select_from(ServerORM)
        if not include_archived:
            stmt = stmt.where(ServerORM.archived_at.is_(None))
        return int((await self._session.execute(stmt)).scalar_one())

    async def deactivate(self, server_id: int) -> Optional[ServerORM]:
        return await self.update(server_id, is_active=False, enabled=False, status=ServerORM.STATUS_DISABLED)
