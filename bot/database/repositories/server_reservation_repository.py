from __future__ import annotations
from datetime import datetime,timezone
from sqlalchemy import func,select
from database.models.server_reservation import ServerCapacityReservationORM
from database.models.server import ServerORM
from .base import BaseRepository
class ServerCapacityReservationRepository(BaseRepository):
 async def get_by_owner(self,owner): return (await self._session.execute(select(ServerCapacityReservationORM).where(ServerCapacityReservationORM.owner_reference==owner).with_for_update())).scalar_one_or_none()
 async def get_for_update(self,token): return (await self._session.execute(select(ServerCapacityReservationORM).where(ServerCapacityReservationORM.public_reservation_id==token).with_for_update())).scalar_one_or_none()
 async def active_count(self,server_id,now): return int((await self._session.execute(select(func.count()).select_from(ServerCapacityReservationORM).where(ServerCapacityReservationORM.server_id==server_id,ServerCapacityReservationORM.status==ServerCapacityReservationORM.STATUS_PENDING,ServerCapacityReservationORM.expires_at>now))).scalar_one())
 async def expire(self,now):
  rows=list((await self._session.execute(select(ServerCapacityReservationORM).where(ServerCapacityReservationORM.status==ServerCapacityReservationORM.STATUS_PENDING,ServerCapacityReservationORM.expires_at<=now).with_for_update())).scalars().all())
  for row in rows: row.status=ServerCapacityReservationORM.STATUS_EXPIRED; row.released_at=now
  return len(rows)
