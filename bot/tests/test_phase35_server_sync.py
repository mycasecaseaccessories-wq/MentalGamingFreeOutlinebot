from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import asyncio
from app.models.server_monitoring import MonitoringPolicy, OperationalHealth, OutlineServerSnapshot, SyncReason
from app.services.outline_server_sync_service import OutlineServerSyncService

def row(**extra):
    base=dict(maintenance_mode=False,health_status='unknown',status='unknown',api_compatible=True,metrics_available=True,existing_key_count=0,outline_version=None,provider_server_id=None,last_health_check_at=None,last_sync_success_at=None,last_sync_failure_at=None,last_sync_at=None,last_sync_attempt_at=None,response_time_ms=None,health_reason=None,consecutive_failures=0,consecutive_successes=0,stale_data=True,used_traffic_bytes=0,metadata_json={}); base.update(extra); return SimpleNamespace(**base)
def snapshot(latency=50, metrics=True): return OutlineServerSnapshot('srv','outline-1',datetime.now(timezone.utc),latency,True,True,'1.10',7,metrics,False,None,None,{})
def service(): return object.__new__(OutlineServerSyncService)
def test_optional_metrics_failure_is_degraded_not_offline():
    svc=service(); svc.policy=MonitoringPolicy(); health,reason=svc.evaluate_health(row(),snapshot(metrics=False)); assert health==OperationalHealth.DEGRADED and reason==SyncReason.PARTIAL_METRICS
def test_repeated_connection_failures_reach_offline_and_mark_stale():
    svc=service(); svc.policy=MonitoringPolicy(failure_threshold=3); r=row()
    for _ in range(3): health=svc._failure(r,SyncReason.TIMEOUT)
    assert health==OperationalHealth.OFFLINE and r.status=='offline' and r.stale_data

def test_maintenance_overrides_automatic_health():
    svc=service(); svc.policy=MonitoringPolicy(); health,reason=svc.evaluate_health(row(maintenance_mode=True),snapshot()); assert health==OperationalHealth.MAINTENANCE and reason==SyncReason.OK
def test_stale_data_after_policy_window():
    svc=service(); svc.policy=MonitoringPolicy(stale_after_seconds=60); assert svc.detect_stale_data(row(last_health_check_at=datetime.now(timezone.utc)-timedelta(seconds=61)))
def test_same_server_lock_is_shared():
    svc=service(); svc._locks={}; svc._guard=asyncio.Lock()
    async def check():
        first=await svc._lock('srv'); second=await svc._lock('srv'); assert first is second; await first.acquire(); assert first.locked(); first.release()
    asyncio.run(check())
