from decimal import Decimal
import pytest
from app.models.vpn_limits import VPNDataLimitPolicy, VPNLimitStatus
from app.services.vpn_data_limit_service import GB_BYTES, VPNDataLimitService
def test_gib_conversion():
    assert VPNDataLimitService._gb_to_bytes(Decimal('10.00')) == 10 * GB_BYTES
def test_validation():
    with pytest.raises(ValueError): VPNDataLimitPolicy(0,'order_snapshot','ORD-1').validate()
    with pytest.raises(ValueError): VPNDataLimitPolicy(10*GB_BYTES,'order_snapshot','ORD-1').validate(maximum_bytes=5*GB_BYTES)
def test_remaining_clamps():
    assert VPNDataLimitService._remaining(10*GB_BYTES,12*GB_BYTES)==0
    assert VPNDataLimitService._remaining(10*GB_BYTES,3*GB_BYTES)==7*GB_BYTES
def test_state_is_separate():
    assert VPNLimitStatus.APPLIED.value=='applied'
    assert VPNLimitStatus.DRIFTED.value!='active'
