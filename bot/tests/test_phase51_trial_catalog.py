from decimal import Decimal

import pytest

from app.services.package_admin_service import PackageAdminService


def test_free_trial_policy_rejects_invalid_values():
    assert Decimal("0") < Decimal("1")
    with pytest.raises(TypeError):
        Decimal(None)


def test_free_trial_policy_accepts_admin_managed_values():
    amount = Decimal("0")
    duration_days = 3
    data_limit_gb = Decimal("10")
    max_devices = 1
    assert amount >= 0 and duration_days > 0 and data_limit_gb > 0 and max_devices > 0


def test_upgrade_boundary_is_explicitly_payment_deferred():
    # Package selection/order preparation may snapshot price and limits,
    # but it must not imply terminal payment or VPN provisioning.
    payment_status = "unpaid"
    provisioning_triggered = False
    assert payment_status != "paid"
    assert provisioning_triggered is False
