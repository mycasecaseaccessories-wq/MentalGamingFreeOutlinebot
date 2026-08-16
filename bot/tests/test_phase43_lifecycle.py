from datetime import datetime,timezone,timedelta
import pytest
from app.models.enums import VPNKeyStatus
from app.models.vpn_lifecycle import VPNLifecyclePolicy,VPNKeyStateMachine

def test_duration_and_utc_expiry():
 p=VPNLifecyclePolicy(max_duration_days=30); a=datetime(2026,8,16,10,tzinfo=timezone.utc); assert p.calculate_expires_at(a,30)==datetime(2026,9,15,10,tzinfo=timezone.utc)
def test_invalid_duration():
 with pytest.raises(ValueError): VPNLifecyclePolicy(max_duration_days=30).validate_duration(0)
def test_expiry_boundary():
 p=VPNLifecyclePolicy(); n=datetime.now(timezone.utc); assert p.is_expired(n,now=n); assert not p.is_expired(n+timedelta(seconds=1),now=n)
def test_terminal_revoke_rules():
 with pytest.raises(ValueError): VPNKeyStateMachine.validate_transition(VPNKeyStatus.REVOKED.value,VPNKeyStatus.ACTIVE.value)
 VPNKeyStateMachine.validate_transition(VPNKeyStatus.EXPIRED.value,VPNKeyStatus.REVOKED.value)
