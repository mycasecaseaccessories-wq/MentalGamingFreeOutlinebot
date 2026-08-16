from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
class OperationalHealth(StrEnum):
    UNKNOWN='unknown'; HEALTHY='healthy'; DEGRADED='degraded'; UNHEALTHY='unhealthy'; OFFLINE='offline'; MAINTENANCE='maintenance'
class SyncReason(StrEnum):
    OK='ok'; TIMEOUT='timeout'; CONNECTION_REFUSED='connection_refused'; INVALID_CREDENTIAL='invalid_credential'; API_INCOMPATIBLE='api_incompatible'; HIGH_LATENCY='high_latency'; PARTIAL_METRICS='partial_metrics'; STALE_DATA='stale_data'; UNKNOWN_ERROR='unknown_error'
@dataclass(frozen=True, slots=True)
class OutlineServerSnapshot:
    server_id:str; provider_server_id:str|None; checked_at:datetime; response_time_ms:int|None; api_reachable:bool; api_compatible:bool; outline_version:str|None; access_key_count:int|None; metrics_available:bool; traffic_available:bool; total_usage_bytes:int|None; measured_at:datetime|None; safe_provider_metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    max_concurrency:int=5; stale_after_seconds:int=900; latency_warning_ms:int=1500; failure_threshold:int=3; recovery_threshold:int=2; sync_interval_seconds:int=300; enabled:bool=True
@dataclass(frozen=True, slots=True)
class ServerOperationalSnapshot:
    server_id:str; health:str; status:str; reason:str; api_reachable:bool; api_compatible:bool; response_time_ms:int|None; access_key_count:int|None; metrics_available:bool; traffic_available:bool; used_traffic_bytes:int|None; stale:bool; consecutive_failures:int; consecutive_successes:int; checked_at:datetime|None; last_sync_attempt_at:datetime|None; last_sync_success_at:datetime|None; last_sync_failure_at:datetime|None
@dataclass(frozen=True, slots=True)
class SyncResult:
    server_id:str; success:bool; health:str; reason:str; snapshot:OutlineServerSnapshot|None=None; stale:bool=False; skipped:bool=False; error_code:str|None=None
@dataclass(frozen=True, slots=True)
class SyncAllResult:
    attempted:int; succeeded:int; failed:int; skipped:int; results:tuple[SyncResult,...]
