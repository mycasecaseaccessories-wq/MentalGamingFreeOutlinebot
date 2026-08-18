from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.maintenance_service import MaintenanceBlockedError, MaintenanceService
from database.connection import DatabaseManager
from database.models.maintenance import IncidentSeverity, MaintenanceScope, MaintenanceState, MaintenanceWindowStatus


def _url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'phase75.db'}"


@pytest.fixture
async def service(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    yield MaintenanceService(db=db)
    await db.close()
    DatabaseManager._instance = None


@pytest.mark.asyncio
async def test_global_and_scoped_precedence_and_selective_degradation(service):
    await service.schedule_maintenance(scope=MaintenanceScope.GLOBAL, state=MaintenanceState.DEGRADED, created_by=1)
    assert await service.is_operation_allowed(MaintenanceScope.PAYMENTS, "VIEW") is True
    assert await service.is_operation_allowed(MaintenanceScope.PAYMENTS, "CREATE") is False

    await service.schedule_maintenance(scope=MaintenanceScope.PAYMENTS, state=MaintenanceState.EMERGENCY, created_by=1)
    effective = await service.get_effective_state(MaintenanceScope.PAYMENTS)
    assert effective["state"] == MaintenanceState.EMERGENCY.value
    assert effective["source"] == MaintenanceScope.PAYMENTS.value
    assert await service.is_operation_allowed(MaintenanceScope.PAYMENTS, "FINALIZE_EXISTING_PAYMENT") is True

    with pytest.raises(MaintenanceBlockedError):
        await service.assert_operation_allowed(MaintenanceScope.PAYMENTS, "PURCHASE")


@pytest.mark.asyncio
async def test_safe_exit_requires_recovery_check(service):
    window = await service.schedule_maintenance(scope=MaintenanceScope.VPN_PROVISIONING, created_by=7)
    blocked = await service.end_maintenance(window["public_id"], ended_by=7, recovery_ok=False)
    assert blocked["ended"] is False
    assert blocked["safe_error_code"] == "recovery_check_failed"

    ended = await service.end_maintenance(window["public_id"], ended_by=7, recovery_ok=True)
    assert ended["ended"] is True
    assert ended["window"]["status"] == MaintenanceWindowStatus.COMPLETED.value
    assert (await service.get_effective_state(MaintenanceScope.VPN_PROVISIONING))["state"] == MaintenanceState.NORMAL.value


@pytest.mark.asyncio
async def test_scheduled_window_activates_only_when_due(service):
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    window = await service.schedule_maintenance(scope=MaintenanceScope.FREE_TRIAL, starts_at=future, created_by=2)
    assert window["status"] == MaintenanceWindowStatus.SCHEDULED.value
    assert (await service.get_effective_state(MaintenanceScope.FREE_TRIAL))["state"] == MaintenanceState.NORMAL.value

    result = await service.activate_due_windows(at=future + timedelta(seconds=1))
    assert result["activated"] == 1
    assert (await service.get_effective_state(MaintenanceScope.FREE_TRIAL, at=future + timedelta(seconds=1)))["state"] == MaintenanceState.MAINTENANCE.value


@pytest.mark.asyncio
async def test_incident_is_safe_summary_and_queryable(service):
    incident = await service.create_incident(title="Payments provider degraded", incident_type="payment_outage", severity=IncidentSeverity.ERROR.value, created_by=9, safe_summary="New payment initiation is limited while the provider is checked.")
    rows = await service.list_incidents(active_only=True)
    assert rows[0]["public_id"] == incident["public_id"]
    assert rows[0]["safe_summary"] == "New payment initiation is limited while the provider is checked."


@pytest.mark.asyncio
async def test_alert_suppression_is_scoped_and_planned(service):
    await service.schedule_maintenance(scope=MaintenanceScope.PAYMENTS, state=MaintenanceState.MAINTENANCE, created_by=11, alert_suppression_policy="scoped")
    suppressed = await service.is_alert_suppressed(MaintenanceScope.PAYMENTS, "payment.failure.spike")
    assert suppressed["suppressed"] is True
    assert suppressed["reason"] == "planned_maintenance"
    unrelated = await service.is_alert_suppressed(MaintenanceScope.VPN_PROVISIONING, "vpn.server.down")
    assert unrelated["suppressed"] is False


@pytest.mark.asyncio
async def test_control_action_is_idempotent_and_audited(service):
    key = "maintenance:test:idempotent"
    first = await service.schedule_maintenance(scope=MaintenanceScope.ORDERS, created_by=12, idempotency_key=key)
    second = await service.schedule_maintenance(scope=MaintenanceScope.ORDERS, created_by=12, idempotency_key=key)
    assert first["public_id"] == second["public_id"]
    async with service.db.session() as session:
        from sqlalchemy import func, select
        from database.models.audit_log import AuditLogORM
        from database.models.maintenance import MaintenanceActionORM
        assert await session.scalar(select(func.count(MaintenanceActionORM.id)).where(MaintenanceActionORM.idempotency_key == key)) == 1
        assert await session.scalar(select(func.count(AuditLogORM.id)).where(AuditLogORM.action == "maintenance.schedule")) == 1


@pytest.mark.asyncio
async def test_control_action_rate_limit_and_force_bypass(service):
    for index in range(service._CONTROL_ACTION_LIMIT):
        await service.schedule_maintenance(scope=MaintenanceScope.ORDERS, created_by=20, idempotency_key=f"maintenance:rate:{index}", starts_at=datetime.now(timezone.utc) + timedelta(minutes=index + 1))
    with pytest.raises(RuntimeError, match="maintenance_rate_limited"):
        await service.schedule_maintenance(scope=MaintenanceScope.ORDERS, created_by=20, idempotency_key="maintenance:rate:blocked", starts_at=datetime.now(timezone.utc) + timedelta(hours=2))
    window = await service.schedule_maintenance(scope=MaintenanceScope.WALLET_WRITE, created_by=21)
    denied = await service.end_maintenance(window["public_id"], ended_by=21, force=True)
    assert denied["safe_error_code"] == "bypass_not_authorized"
