from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from enum import StrEnum
from app.models.enums import VPNKeyStatus
class ProviderCleanupStatus(StrEnum): NOT_REQUIRED='not_required'; PENDING='pending'; COMPLETED='completed'; FAILED='failed'
class LifecycleReason(StrEnum): EXPIRY='expiry'; ADMIN='admin'; POLICY='policy'; SECURITY='security'; PAYMENT='payment'; OTHER='other'
@dataclass(frozen=True,slots=True)
class VPNLifecyclePolicy:
    max_duration_days:int=3650; grace_period_minutes:int=0; expiring_soon_hours:int=72
    def validate_duration(self,duration_days:int)->int:
        if isinstance(duration_days,bool) or not isinstance(duration_days,int) or duration_days<=0 or duration_days>self.max_duration_days: raise ValueError('invalid duration_days')
        return duration_days
    def calculate_expires_at(self,activated_at:datetime,duration_days:int)->datetime:
        a=self._aware(activated_at); return a+timedelta(days=self.validate_duration(duration_days))
    def is_expired(self,expires_at,*,now=None): return expires_at is not None and self._aware(now or datetime.now(timezone.utc))>=self._aware(expires_at)
    def is_expiring_soon(self,expires_at,*,now=None): return expires_at is not None and not self.is_expired(expires_at,now=now) and self._aware(expires_at)<=self._aware(now or datetime.now(timezone.utc))+timedelta(hours=self.expiring_soon_hours)
    def remaining(self,expires_at,*,now=None): return None if expires_at is None else max(self._aware(expires_at)-self._aware(now or datetime.now(timezone.utc)),timedelta(0))
    @staticmethod
    def _aware(v): return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
class VPNKeyStateMachine:
    _ALLOWED={VPNKeyStatus.PENDING.value:{VPNKeyStatus.ACTIVE.value,VPNKeyStatus.REVOKED.value},VPNKeyStatus.ACTIVE.value:{VPNKeyStatus.SUSPENDED.value,VPNKeyStatus.EXPIRED.value,VPNKeyStatus.REVOKED.value},VPNKeyStatus.SUSPENDED.value:{VPNKeyStatus.ACTIVE.value,VPNKeyStatus.EXPIRED.value,VPNKeyStatus.REVOKED.value},VPNKeyStatus.EXPIRED.value:{VPNKeyStatus.REVOKED.value},VPNKeyStatus.REVOKED.value:set()}
    @classmethod
    def validate_transition(cls,current,target):
        if current!=target and target not in cls._ALLOWED.get(current,set()): raise ValueError(f'Invalid VPN key lifecycle transition: {current} -> {target}')
@dataclass(frozen=True,slots=True)
class VPNLifecycleSummary:
    key_id:int; status:str; activated_at:datetime|None; expires_at:datetime|None; remaining:timedelta|None; expiring_soon:bool; provider_cleanup_status:str
