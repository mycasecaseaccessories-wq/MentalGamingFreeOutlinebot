from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Callable

from app.services.background_job_dispatcher import BackgroundJobDispatcher
from database.models.background_job import BackgroundJobORM
logger=logging.getLogger(__name__)
try:
 from apscheduler.schedulers.asyncio import AsyncIOScheduler
 _APSCHEDULER_AVAILABLE=True
except ImportError:
 AsyncIOScheduler=None
 _APSCHEDULER_AVAILABLE=False
class Scheduler:
 def __init__(self):
  self._scheduler=AsyncIOScheduler() if _APSCHEDULER_AVAILABLE else None
  self.logger=logging.getLogger(__name__)
  self.job_service=None
  self.dispatcher=None

 def register_jobs(self,*,sync_service=None,reservation_service=None,lifecycle_service=None,job_service=None,health_service=None,alert_service=None,order_service=None,free_trial_upgrade_service=None,backup_service=None,maintenance_service=None,lifecycle_interval_seconds=120,lifecycle_batch_size=100):
  self.job_service = job_service
  if job_service is None:
   if sync_service is not None:self.add_job(sync_service.sync_all,'interval',seconds=sync_service.policy.sync_interval_seconds,jitter=30,id='outline-server-sync',replace_existing=True,max_instances=1,coalesce=True)
   if reservation_service is not None:self.add_job(reservation_service.expire_reservations,'interval',minutes=1,id='server-reservation-cleanup',replace_existing=True,max_instances=1,coalesce=True)
   if lifecycle_service is not None:
    from app.tasks.vpn_expiration import VPNExpirationSweepTask
    sweep=VPNExpirationSweepTask(db=lifecycle_service.db,lifecycle_service=lifecycle_service,batch_size=lifecycle_batch_size)
    self.add_job(sweep.run,'interval',seconds=max(60,int(lifecycle_interval_seconds)),id='vpn-expiration-sweep',replace_existing=True,max_instances=1,coalesce=True)
   return

  self.dispatcher = BackgroundJobDispatcher(job_service)
  if sync_service is not None:
   self.dispatcher.register_handler(BackgroundJobORM.JOB_VPN_LIFECYCLE_SYNC, lambda _payload: sync_service.sync_all(trigger='scheduled'))
   self._register_periodic(BackgroundJobORM.JOB_VPN_LIFECYCLE_SYNC, max(60, int(sync_service.policy.sync_interval_seconds)))
  if reservation_service is not None:
   self.dispatcher.register_handler("server_reservation_cleanup", lambda _payload: reservation_service.expire_reservations())
   self._register_periodic("server_reservation_cleanup", 60)
  if lifecycle_service is not None:
   from app.tasks.vpn_expiration import VPNExpirationSweepTask
   sweep=VPNExpirationSweepTask(db=lifecycle_service.db,lifecycle_service=lifecycle_service,batch_size=lifecycle_batch_size)
   self.dispatcher.register_handler(BackgroundJobORM.JOB_VPN_EXPIRATION, lambda _payload: sweep.run())
   self._register_periodic(BackgroundJobORM.JOB_VPN_EXPIRATION, max(60, int(lifecycle_interval_seconds)))
  if order_service is not None:
   self.dispatcher.register_handler(BackgroundJobORM.JOB_ORDER_EXPIRATION, lambda _payload: order_service.expire_pending_orders())
   self._register_periodic(BackgroundJobORM.JOB_ORDER_EXPIRATION, 60)
  if free_trial_upgrade_service is not None:
   self.dispatcher.register_handler(BackgroundJobORM.JOB_FREE_TRIAL_EXPIRATION, lambda _payload: free_trial_upgrade_service.recover_pending_fulfillment(limit=50))
   self._register_periodic(BackgroundJobORM.JOB_FREE_TRIAL_EXPIRATION, 120)
  if health_service is not None:
   async def _health_check_and_evaluate(_payload):
    snapshot = await health_service.check_system()
    if alert_service is not None:
     for result in snapshot.components:
      if result.component == "outline_apis":
       await alert_service.evaluate_health_result(result)
    return snapshot
   self.dispatcher.register_handler(BackgroundJobORM.JOB_HEALTH_CHECK, _health_check_and_evaluate)
   self._register_periodic(BackgroundJobORM.JOB_HEALTH_CHECK, 300)
  if backup_service is not None:
   self.dispatcher.register_handler(BackgroundJobORM.JOB_BACKUP_CREATION, lambda _payload: backup_service.create_backup(backup_type='automatic', retention_class='daily'))
   self.dispatcher.register_handler(BackgroundJobORM.JOB_BACKUP_RETENTION, lambda _payload: backup_service.apply_retention())
   self.dispatcher.register_handler(BackgroundJobORM.JOB_BACKUP_RESTORE_TEST, lambda _payload: backup_service.run_latest_restore_test())
   self._register_periodic(BackgroundJobORM.JOB_BACKUP_CREATION, 3600)
   self._register_periodic(BackgroundJobORM.JOB_BACKUP_RETENTION, 86400)
   self._register_periodic(BackgroundJobORM.JOB_BACKUP_RESTORE_TEST, 604800)
  if maintenance_service is not None:
   self.dispatcher.register_handler(BackgroundJobORM.JOB_MAINTENANCE_ACTIVATION, lambda _payload: maintenance_service.process_due_windows())
   self.dispatcher.register_handler(BackgroundJobORM.JOB_MAINTENANCE_RECOVERY_CHECK, lambda _payload: maintenance_service.maintenance_recovery_snapshot())
   self._register_periodic(BackgroundJobORM.JOB_MAINTENANCE_ACTIVATION, 30)
   self._register_periodic(BackgroundJobORM.JOB_MAINTENANCE_RECOVERY_CHECK, 300)
  self.add_job(self.dispatcher.run_once, 'interval', seconds=5, id='durable-job-dispatcher', replace_existing=True, max_instances=1, coalesce=True)

 def _register_periodic(self, job_type: str, cadence_seconds: int):
  self.add_job(self._enqueue_periodic, 'interval', seconds=cadence_seconds, id=f'durable-enqueue-{job_type}', replace_existing=True, max_instances=1, coalesce=True, kwargs={'job_type': job_type, 'cadence_seconds': cadence_seconds})

 async def _enqueue_periodic(self, *, job_type: str, cadence_seconds: int):
  now = datetime.now(timezone.utc)
  bucket = int(now.timestamp()) // max(1, cadence_seconds)
  await self.job_service.enqueue(job_type=job_type, logical_key=f'{job_type}:{bucket}', scheduled_for=now, payload_safe={'scheduled_bucket': bucket})
 def add_job(self,func:Callable,trigger:str,**kwargs):
  if self._scheduler is None:return
  self._scheduler.add_job(func,trigger,**kwargs)
 def start(self):
  if self._scheduler is not None:self._scheduler.start()
 def shutdown(self):
  if self._scheduler is not None and self._scheduler.running:self._scheduler.shutdown(wait=False)
