from dataclasses import dataclass
from enum import StrEnum
from app.models.enums import VPNKeyStatus
class DeviceLimitStatus(StrEnum): NOT_CONFIGURED='not_configured'; ALLOWED='allowed'; BLOCKED='blocked'; UNKNOWN='unknown'
@dataclass(frozen=True,slots=True)
class DevicePolicy:
 limit:int|None; fail_closed:bool=True
 def validate(self):
  if self.limit is not None and (isinstance(self.limit,bool) or not isinstance(self.limit,int) or self.limit<=0): raise ValueError('device limit must be a positive integer')
 def decide(self,*,known_devices):
  self.validate()
  if self.limit is None:return DeviceLimitStatus.NOT_CONFIGURED
  if known_devices is None:return DeviceLimitStatus.BLOCKED if self.fail_closed else DeviceLimitStatus.UNKNOWN
  return DeviceLimitStatus.ALLOWED if known_devices<self.limit else DeviceLimitStatus.BLOCKED
@dataclass(frozen=True,slots=True)
class SecureConnectionInfo:
 key_id:int; access_url:str; server_name:str|None; country:str|None; status:str; device_status:DeviceLimitStatus
 def __repr__(self):return f"SecureConnectionInfo(key_id={self.key_id!r}, access_url='<redacted>', status={self.status!r}, device_status={self.device_status!r})"
def can_deliver_secret(*,status,is_active,device_status):return status==VPNKeyStatus.ACTIVE.value and is_active and device_status in {DeviceLimitStatus.ALLOWED,DeviceLimitStatus.NOT_CONFIGURED}
