from __future__ import annotations
import logging
from typing import Callable
logger=logging.getLogger(__name__)
try:
 from apscheduler.schedulers.asyncio import AsyncIOScheduler
 _APSCHEDULER_AVAILABLE=True
except ImportError:
 AsyncIOScheduler=None
 _APSCHEDULER_AVAILABLE=False
class Scheduler:
 def __init__(self): self._scheduler=AsyncIOScheduler() if _APSCHEDULER_AVAILABLE else None; self.logger=logging.getLogger(__name__)
 def register_jobs(self,*,sync_service=None,reservation_service=None,lifecycle_service=None,lifecycle_interval_seconds=120,lifecycle_batch_size=100):
  if sync_service is not None:self.add_job(sync_service.sync_all,'interval',seconds=sync_service.policy.sync_interval_seconds,jitter=30,id='outline-server-sync',replace_existing=True,max_instances=1,coalesce=True)
  if reservation_service is not None:self.add_job(reservation_service.expire_reservations,'interval',minutes=1,id='server-reservation-cleanup',replace_existing=True,max_instances=1,coalesce=True)
  if lifecycle_service is not None:
   from app.tasks.vpn_expiration import VPNExpirationSweepTask
   sweep=VPNExpirationSweepTask(db=lifecycle_service.db,lifecycle_service=lifecycle_service,batch_size=lifecycle_batch_size)
   self.add_job(sweep.run,'interval',seconds=max(60,int(lifecycle_interval_seconds)),id='vpn-expiration-sweep',replace_existing=True,max_instances=1,coalesce=True)
 def add_job(self,func:Callable,trigger:str,**kwargs):
  if self._scheduler is None:return
  self._scheduler.add_job(func,trigger,**kwargs)
 def start(self):
  if self._scheduler is not None:self._scheduler.start()
 def shutdown(self):
  if self._scheduler is not None and self._scheduler.running:self._scheduler.shutdown(wait=False)
