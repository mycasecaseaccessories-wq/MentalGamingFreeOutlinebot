from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from time import perf_counter
from sqlalchemy import select
from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.integrations.outline_client import OutlineAPIClient, OutlineAPIError
from app.models.outline_setup import OutlineCredentialInput
from app.models.server_monitoring import MonitoringPolicy, OperationalHealth, OutlineServerSnapshot, ServerOperationalSnapshot, SyncAllResult, SyncReason, SyncResult
from app.security.credential_vault import CredentialVault
from app.security.outline_url_policy import UnsafeOutlineURL, validate_outline_url
from database.models.server import ServerORM
from .base import BaseService
class OutlineServerSyncService(BaseService):
    def __init__(self,db=None,*,client=None,vault=None,policy=None):
        super().__init__(db); self.client=client or OutlineAPIClient(); self.vault=vault or CredentialVault(); self.policy=policy or MonitoringPolicy(); self._locks={}; self._guard=asyncio.Lock()
    async def _lock(self,sid):
        async with self._guard: return self._locks.setdefault(sid,asyncio.Lock())
    async def sync_server(self,server_id:str,*,trigger='scheduled')->Result[SyncResult]:
        lock=await self._lock(server_id)
        if lock.locked(): return Success(SyncResult(server_id,False,'unknown','sync_in_progress',skipped=True,error_code='sync_in_progress'))
        async with lock: return await self._sync_locked(server_id,trigger)
    async def sync_all(self,*,trigger='scheduled')->SyncAllResult:
        async with self.db.session() as s: rows=list((await s.execute(select(ServerORM).where(ServerORM.provider_type=='outline',ServerORM.archived_at.is_(None),ServerORM.api_url.is_not(None),ServerORM.credential_ciphertext.is_not(None)))).scalars().all())
        sem=asyncio.Semaphore(max(1,self.policy.max_concurrency))
        async def one(row):
            async with sem:
                r=await self.sync_server(row.public_server_id,trigger=trigger); return r.unwrap() if r.is_success else SyncResult(row.public_server_id,False,'unknown',r.error.code if r.error else 'unknown_error',error_code=r.error.code if r.error else None)
        results=tuple(await asyncio.gather(*(one(r) for r in rows)))
        return SyncAllResult(len(results),sum(x.success for x in results),sum(not x.success and not x.skipped for x in results),sum(x.skipped for x in results),results)
    async def health_check(self,server_id): return await self.sync_server(server_id,trigger='health_check')
    async def get_sync_status(self,server_id): return await self.get_server_health(server_id)
    async def get_server_health(self,server_id):
        async with self.db.session() as s: row=(await s.execute(select(ServerORM).where(ServerORM.public_server_id==server_id))).scalar_one_or_none()
        return Failure('not_found','Server not found.') if row is None else Success(self._snapshot(row))
    async def get_server_usage_summary(self,server_id):
        r=await self.get_server_health(server_id)
        if r.is_failure:return r
        v=r.unwrap(); return Success({'server_id':server_id,'traffic_available':v.traffic_available,'used_traffic_bytes':v.used_traffic_bytes,'access_key_count':v.access_key_count,'stale':v.stale,'measured_at':v.checked_at})
    def detect_stale_data(self,row,now=None):
        checked=row.last_health_check_at or row.last_sync_success_at
        return checked is None or (now or datetime.now(timezone.utc))-self._aware(checked)>timedelta(seconds=self.policy.stale_after_seconds)
    async def _sync_locked(self,sid,trigger):
        now=datetime.now(timezone.utc)
        async with self.db.session() as s:
            row=(await s.execute(select(ServerORM).where(ServerORM.public_server_id==sid).with_for_update())).scalar_one_or_none()
            if row is None:return Failure('not_found','Server not found.')
            if row.archived_at is not None:return Failure('archived','Server is archived.')
            if row.provider_type!='outline' or not row.api_url or not row.credential_ciphertext:return Failure('unsupported_integration','Server has no supported Outline integration.')
            row.last_sync_attempt_at=now
            try:
                raw=self.vault.decrypt(row.credential_ciphertext); validated=await validate_outline_url(raw,allow_private=True); started=perf_counter(); d=await self.client.verify_management_api(validated,OutlineCredentialInput(raw,row.cert_sha256,'monitoring')); latency=int((perf_counter()-started)*1000)
                snap=OutlineServerSnapshot(sid,d.provider_server_id,d.verified_at,latency,True,d.api_compatible,d.outline_version,d.existing_key_count,d.metrics_available,False,None,None,d.safe_metadata); health,reason=self.evaluate_health(row,snap); self._success(row,snap,health,reason); await s.flush()
            except Exception as exc:
                reason=self._reason(exc); health=self._failure(row,reason); await s.flush(); await bus.emit(EventType.SERVER_SYNC_FAILED,public_server_id=sid,reason=reason.value,trigger=trigger); return Success(SyncResult(sid,False,health.value,reason.value,stale=True,error_code=reason.value))
        await bus.emit(EventType.SERVER_SYNC_COMPLETED,public_server_id=sid,health=health.value,reason=reason.value,trigger=trigger); return Success(SyncResult(sid,True,health.value,reason.value,snapshot=snap))
    def evaluate_health(self,row,snap):
        if row.maintenance_mode:return OperationalHealth.MAINTENANCE,SyncReason.OK
        if snap.response_time_ms and snap.response_time_ms>self.policy.latency_warning_ms:return OperationalHealth.DEGRADED,SyncReason.HIGH_LATENCY
        if not snap.metrics_available:return OperationalHealth.DEGRADED,SyncReason.PARTIAL_METRICS
        return OperationalHealth.HEALTHY,SyncReason.OK
    def _success(self,row,snap,health,reason):
        row.status=ServerORM.STATUS_MAINTENANCE if row.maintenance_mode else ServerORM.STATUS_ONLINE; row.health_status=health.value; row.api_compatible=snap.api_compatible; row.metrics_available=snap.metrics_available; row.existing_key_count=snap.access_key_count; row.outline_version=snap.outline_version; row.provider_server_id=snap.provider_server_id or row.provider_server_id; row.last_health_check_at=snap.checked_at; row.last_sync_success_at=snap.checked_at; row.last_sync_failure_at=None; row.last_sync_at=snap.checked_at; row.response_time_ms=snap.response_time_ms; row.health_reason=reason.value; row.consecutive_failures=0; row.consecutive_successes=(row.consecutive_successes or 0)+1; row.stale_data=False; row.metadata_json={**(row.metadata_json or {}),**snap.safe_provider_metadata}
    def _failure(self,row,reason):
        now=datetime.now(timezone.utc); row.last_health_check_at=now; row.last_sync_failure_at=now; row.health_reason=reason.value; row.consecutive_failures=(row.consecutive_failures or 0)+1; row.consecutive_successes=0; row.stale_data=True
        if reason in {SyncReason.TIMEOUT,SyncReason.CONNECTION_REFUSED} and row.consecutive_failures>=self.policy.failure_threshold: row.status=ServerORM.STATUS_OFFLINE; row.health_status='offline'; return OperationalHealth.OFFLINE
        if row.consecutive_failures>=self.policy.failure_threshold: row.health_status='unhealthy'; return OperationalHealth.UNHEALTHY
        row.health_status='degraded'; return OperationalHealth.DEGRADED
    def _snapshot(self,row):
        stale=self.detect_stale_data(row) or bool(row.stale_data); return ServerOperationalSnapshot(row.public_server_id,row.health_status,row.status,row.health_reason or ('stale_data' if stale else 'unknown_error'),row.status!='offline',row.api_compatible,row.response_time_ms,row.existing_key_count,row.metrics_available,False,row.used_traffic_bytes,stale,row.consecutive_failures or 0,row.consecutive_successes or 0,row.last_health_check_at,row.last_sync_attempt_at,row.last_sync_success_at,row.last_sync_failure_at)
    @staticmethod
    def _reason(exc):
        text=str(exc).lower()
        if isinstance(exc,(TimeoutError,asyncio.TimeoutError)) or 'timeout' in text or 'timed out' in text:return SyncReason.TIMEOUT
        if 'refused' in text:return SyncReason.CONNECTION_REFUSED
        if isinstance(exc,UnsafeOutlineURL) or 'credential' in text or '401' in text or '403' in text:return SyncReason.INVALID_CREDENTIAL
        if isinstance(exc,OutlineAPIError) and 'incompatible' in text:return SyncReason.API_INCOMPATIBLE
        return SyncReason.UNKNOWN_ERROR
    @staticmethod
    def _aware(value):return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
