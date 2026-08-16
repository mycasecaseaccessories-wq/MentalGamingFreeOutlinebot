from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
class VPNLimitStatus(StrEnum):
    NOT_CONFIGURED='not_configured'; PENDING='pending'; APPLIED='applied'; FAILED='failed'; UNSUPPORTED='unsupported'; DRIFTED='drifted'
@dataclass(frozen=True, slots=True)
class VPNDataLimitPolicy:
    limit_bytes:int; source:str; source_reference:str; enforcement_required:bool=True; applied_at:datetime|None=None; provider_verified:bool=False
    def validate(self,*,maximum_bytes:int|None=None):
        if not isinstance(self.limit_bytes,int) or isinstance(self.limit_bytes,bool) or self.limit_bytes<=0: raise ValueError('limit_bytes must be a positive integer')
        if maximum_bytes is not None and self.limit_bytes>maximum_bytes: raise ValueError('limit_bytes exceeds configured maximum')
@dataclass(frozen=True, slots=True)
class RemoteKeyUsage:
    provider_key_id:int; used_bytes:int; measured_at:datetime
@dataclass(frozen=True, slots=True)
class VPNLimitApplicationResult:
    key_id:int; operation_id:str; limit_bytes:int; status:VPNLimitStatus; provider_verified:bool; used_bytes:int; remaining_bytes:int; last_usage_sync_at:datetime|None=None
