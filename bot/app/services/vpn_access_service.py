from app.models.vpn_access import DeviceLimitStatus,DevicePolicy,SecureConnectionInfo,can_deliver_secret
class VPNAccessService:
 def __init__(self,*,device_fail_closed=True):self.device_fail_closed=device_fail_closed
 def evaluate_device(self,*,device_limit,known_devices):
  p=DevicePolicy(device_limit,fail_closed=self.device_fail_closed);return p.decide(known_devices=known_devices)
 def build_connection_info(self,*,key,server_name,country,known_devices):
  status=self.evaluate_device(device_limit=getattr(key,'device_limit',None),known_devices=known_devices)
  if not can_deliver_secret(status=key.status,is_active=bool(key.is_active),device_status=status):return None
  return SecureConnectionInfo(key.id,key.access_url,server_name,country,key.status,status)
