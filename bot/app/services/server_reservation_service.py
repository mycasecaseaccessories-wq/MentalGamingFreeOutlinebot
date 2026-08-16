from __future__ import annotations
from datetime import datetime,timedelta,timezone
import secrets
from app.core.result import Failure,Success
from app.events import EventType,bus
from database.models.server import ServerORM
from database.models.server_reservation import ServerCapacityReservationORM
from database.repositories.server_repository import ServerRepository
from database.repositories.server_reservation_repository import ServerCapacityReservationRepository
from .base import BaseService
class ServerReservationService(BaseService):
 def __init__(self,db,timeout_seconds=600): super().__init__(db); self.timeout_seconds=timeout_seconds
 async def reserve(self,server_public_id,workload_type,owner_reference):
  now=datetime.now(timezone.utc)
  async with self.db.session() as session:
   repo=ServerCapacityReservationRepository(session); old=await repo.get_by_owner(owner_reference)
   if old and old.status in {old.STATUS_PENDING,old.STATUS_COMMITTED}: return Success(old)
   server=(await session.execute(__import__('sqlalchemy').select(ServerORM).where(ServerORM.public_server_id==server_public_id).with_for_update())).scalar_one_or_none()
   if server is None:return Failure('server_not_found','Server not found.')
   if server.max_users is None:return Failure('capacity_unknown','Capacity is unknown; reservation denied.')
   active=await repo.active_count(server.id,now)
   if server.current_users+active>=server.max_users:return Failure('capacity_exhausted','Server capacity exhausted.')
   row=ServerCapacityReservationORM(public_reservation_id='RSV-'+secrets.token_urlsafe(12),server_id=server.id,workload_type=str(workload_type),owner_reference=owner_reference,status=ServerCapacityReservationORM.STATUS_PENDING,created_at=now,expires_at=now+timedelta(seconds=self.timeout_seconds)); session.add(row); await session.flush()
  await bus.emit(EventType.SERVER_CAPACITY_RESERVED,reservation_id=row.public_reservation_id,server_public_id=server_public_id)
  return Success(row)
 async def commit_reservation(self,token): return await self._transition(token,ServerCapacityReservationORM.STATUS_COMMITTED,'committed_at',EventType.SERVER_CAPACITY_RESERVATION_COMMITTED)
 async def release_reservation(self,token): return await self._transition(token,ServerCapacityReservationORM.STATUS_RELEASED,'released_at',EventType.SERVER_CAPACITY_RESERVATION_RELEASED)
 async def _transition(self,token,target,stamp,event):
  now=datetime.now(timezone.utc)
  async with self.db.session() as session:
   row=await ServerCapacityReservationRepository(session).get_for_update(token)
   if row is None:return Failure('reservation_not_found','Reservation not found.')
   if row.status==target:return Success(row)
   if row.status!=ServerCapacityReservationORM.STATUS_PENDING:return Failure('reservation_terminal','Reservation is already terminal.')
   row.status=target; setattr(row,stamp,now); await session.flush()
  await bus.emit(event,reservation_id=token,server_id=row.server_id); return Success(row)
 async def expire_reservations(self):
  async with self.db.session() as session: count=await ServerCapacityReservationRepository(session).expire(datetime.now(timezone.utc))
  return count
