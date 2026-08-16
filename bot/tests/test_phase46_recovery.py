import pytest

from app.models.vpn_recovery import RecoveryStatus, RotationReason, RotationRequest, RenewalRequest


def test_renewal_requires_payment_and_operation_identity():
    request = RenewalRequest(user_id=1, key_id=2, package_id=3, payment_reference="pay-1", idempotency_key="renewal:2:pay-1")
    request.validate()


def test_rotation_identity_is_explicit_and_reasoned():
    request = RotationRequest(user_id=1, key_id=2, reason=RotationReason.COMPROMISED, idempotency_key="rotate:2:incident-1")
    request.validate()
    assert request.reason is RotationReason.COMPROMISED


def test_reconciliation_status_is_not_success():
    assert RecoveryStatus.RECONCILIATION_REQUIRED.value == "reconciliation_required"


@pytest.mark.parametrize("bad", [RenewalRequest(0, 2, 3, "pay", "op"), RotationRequest(1, 0, RotationReason.LOST, "op")])
def test_invalid_identity_is_rejected(bad):
    with pytest.raises(ValueError):
        bad.validate()
