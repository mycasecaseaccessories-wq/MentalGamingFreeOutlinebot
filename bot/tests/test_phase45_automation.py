from types import SimpleNamespace

import pytest

from app.events import EventType
from app.models.vpn_provisioning import ProvisioningSource
from app.services.paid_vpn_automation_service import PaidVPNAutomationService


class FakeResult:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.is_failure = error is not None


class FakeProvisioning:
    def __init__(self):
        self.requests = []

    async def provision(self, request, *, actor_user_id):
        self.requests.append(request)
        return FakeResult(SimpleNamespace(vpn_key_id=42))


class FakeLimits:
    def __init__(self): self.calls = []
    async def apply_for_key(self, **kwargs): self.calls.append(kwargs); return FakeResult(SimpleNamespace())


class FakeLifecycle:
    def __init__(self): self.calls = []
    async def activate_key(self, **kwargs): self.calls.append(kwargs); return FakeResult(SimpleNamespace())


@pytest.mark.asyncio
async def test_non_paid_terminal_event_is_ignored():
    service = PaidVPNAutomationService(db=None, provisioning_service=FakeProvisioning(), data_limit_service=FakeLimits(), lifecycle_service=FakeLifecycle())
    assert await service.handle_terminal_paid_event(order_id=1, user_id=2, payment_status="pending") is None


@pytest.mark.asyncio
async def test_paid_flow_is_order_idempotent_and_ordered(monkeypatch):
    provisioning, limits, lifecycle = FakeProvisioning(), FakeLimits(), FakeLifecycle()
    service = PaidVPNAutomationService(db=None, provisioning_service=provisioning, data_limit_service=limits, lifecycle_service=lifecycle)
    monkeypatch.setattr("app.services.paid_vpn_automation_service.bus.emit", _noop_emit)
    first = await service.provision_paid_order(order_id=9, user_id=2, payment_reference="p-9")
    second = await service.provision_paid_order(order_id=9, user_id=2, payment_reference="p-9")
    assert first.status == second.status == "ready"
    assert provisioning.requests[0].idempotency_key == "paid-order:9"
    assert provisioning.requests[0].source_type == ProvisioningSource.PAID_ORDER
    assert limits.calls[0]["key_id"] == 42
    assert lifecycle.calls[0]["key_id"] == 42


async def _noop_emit(*args, **kwargs):
    return None
