from types import SimpleNamespace
from app.models.vpn_access import DeviceLimitStatus,DevicePolicy
from app.services.vpn_access_service import VPNAccessService
def test_device_limit_blocks_at_limit():
 s=VPNAccessService();assert s.evaluate_device(device_limit=2,known_devices=1)==DeviceLimitStatus.ALLOWED;assert s.evaluate_device(device_limit=2,known_devices=2)==DeviceLimitStatus.BLOCKED
def test_unknown_fails_closed():assert VPNAccessService().evaluate_device(device_limit=1,known_devices=None)==DeviceLimitStatus.BLOCKED
def test_active_gate_and_redacted_repr():
 s=VPNAccessService();k=SimpleNamespace(id=7,access_url='ss://secret',status='active',is_active=True,device_limit=None);i=s.build_connection_info(key=k,server_name='SG-01',country='SG',known_devices=None);assert i and 'ss://secret' not in repr(i);k.status='expired';assert s.build_connection_info(key=k,server_name='SG-01',country='SG',known_devices=None) is None
def test_invalid_limit():
 try:DevicePolicy(0).validate()
 except ValueError:return
 raise AssertionError('invalid limit accepted')
