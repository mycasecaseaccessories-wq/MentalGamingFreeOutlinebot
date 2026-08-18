from datetime import UTC, datetime

import pytest

from app.services.health_service import HealthService, OperationalHealthStatus
from app.services.maintenance_service import MaintenanceService
from app.services.operational_alert_service import OperationalAlertService
from database.connection import DatabaseManager
from database.models.maintenance import AlertStatus, OperationalAlertORM, OperationalIncidentORM


class _Notifications:
    def __init__(self):
        self.messages = []

    async def notify_admins(self, text):
        self.messages.append(text)
        return {"attempted": 1, "delivered": 1, "results": [{"delivered": True}]}


def _url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'phase72-alerts.db'}"


@pytest.fixture
async def alert_service(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    maintenance = MaintenanceService(db=db)
    service = OperationalAlertService(
        db=db, maintenance_service=maintenance, notification_service=_Notifications()
    )
    yield service
    await db.close()
    DatabaseManager._instance = None


@pytest.mark.asyncio
async def test_outline_alert_is_persisted_deduplicated_and_linked_to_one_incident(alert_service):
    first = await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Outline API is unreachable."
    )
    second = await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Outline API is still unreachable."
    )

    assert first["opened"] is True
    assert second["opened"] is False
    assert second["alert"]["occurrence_count"] == 2
    assert second["alert"]["incident_id"] is not None
    assert first["alert"]["fingerprint"] == second["alert"]["fingerprint"]

    async with alert_service.db.session() as session:
        alerts = list(
            (await session.execute(__import__("sqlalchemy").select(OperationalAlertORM)))
            .scalars()
            .all()
        )
        incidents = list(
            (await session.execute(__import__("sqlalchemy").select(OperationalIncidentORM)))
            .scalars()
            .all()
        )
    assert len(alerts) == 1
    assert len(incidents) == 1
    assert incidents[0].status == "open"


@pytest.mark.asyncio
async def test_outline_failure_full_operational_recovery_flow(alert_service):
    class _Scheduler:
        class _Inner:
            running = True

        _scheduler = _Inner()

    health = HealthService(db=alert_service.db, scheduler=_Scheduler())
    provider = {"healthy": True}
    health.set_provider_probe(
        "outline_apis",
        lambda checked_at: OperationalHealthStatus.HEALTHY
        if provider["healthy"]
        else OperationalHealthStatus.UNHEALTHY,
    )

    initial = await health.check_system()
    initial_result = next(item for item in initial.components if item.component == "outline_apis")
    assert initial_result.status == OperationalHealthStatus.HEALTHY

    provider["healthy"] = False
    failed = await health.check_system()
    failed_result = next(item for item in failed.components if item.component == "outline_apis")
    assert failed_result.status == OperationalHealthStatus.UNHEALTHY
    opened = await alert_service.evaluate_health_result(failed_result)
    assert opened["opened"] is True

    maintenance = alert_service.maintenance
    assert opened["maintenance_window"]["status"] == "active"
    assert await maintenance.is_operation_allowed("vpn_provisioning", "CREATE") is False
    assert await maintenance.get_customer_notice("vpn_provisioning", language="en")
    assert await maintenance.get_customer_notice("vpn_provisioning", language="my")

    provider["healthy"] = True
    recovered = await health.check_system()
    recovered_result = next(
        item for item in recovered.components if item.component == "outline_apis"
    )
    assert recovered_result.status == OperationalHealthStatus.HEALTHY
    recovery = await alert_service.recover_component(
        component="outline_apis", now=recovered_result.checked_at
    )
    assert recovery["recovery_check"]["healthy"] is True
    assert recovery["maintenance_end"]["ended"] is True
    assert recovery["alert"]["status"] == AlertStatus.RESOLVED.value
    assert await maintenance.list_incidents(active_only=True) == []


@pytest.mark.asyncio
async def test_outline_failure_runs_scoped_maintenance_customer_notice_and_recovery_exit(
    alert_service,
):
    opened = await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Outline API is unreachable."
    )
    assert opened["maintenance_window"]["status"] == "active"
    assert opened["notification"]["delivered"] == 1

    maintenance = alert_service.maintenance
    assert await maintenance.is_operation_allowed("vpn_provisioning", "CREATE") is False
    assert await maintenance.is_operation_allowed("vpn_provisioning", "VIEW") is True
    assert await maintenance.get_customer_notice("vpn_provisioning", language="en")
    assert await maintenance.get_customer_notice("vpn_provisioning", language="my")

    recovered = await alert_service.recover_component(
        component="outline_apis", now=datetime.now(UTC)
    )
    assert recovered["recovery_check"]["healthy"] is True
    assert recovered["maintenance_end"]["ended"] is True
    assert recovered["alert"]["status"] == AlertStatus.RESOLVED.value

    incidents = await maintenance.list_incidents(active_only=True)
    assert incidents == []


@pytest.mark.asyncio
async def test_outline_recovery_resolves_same_alert_and_incident_idempotently(alert_service):
    opened = await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Provider outage."
    )
    recovered = await alert_service.evaluate_component(
        component="outline_apis", healthy=True, now=datetime.now(UTC)
    )
    repeated = await alert_service.evaluate_component(component="outline_apis", healthy=True)

    assert recovered["resolved"] is True
    assert recovered["alert"]["public_id"] == opened["alert"]["public_id"]
    assert recovered["alert"]["status"] == AlertStatus.RESOLVED.value
    assert repeated["resolved"] is False

    async with alert_service.db.session() as session:
        alert = (
            await session.execute(__import__("sqlalchemy").select(OperationalAlertORM))
        ).scalar_one()
        incident = (
            await session.execute(__import__("sqlalchemy").select(OperationalIncidentORM))
        ).scalar_one()
    assert alert.status == AlertStatus.RESOLVED.value
    assert incident.status == "resolved"


@pytest.mark.asyncio
async def test_repeated_failure_creates_one_alert_incident_and_notification_cycle(alert_service):
    for _ in range(10):
        result = await alert_service.evaluate_component(
            component="outline_apis", healthy=False, safe_summary="Provider unavailable."
        )
    assert result["alert"]["occurrence_count"] == 10
    assert len(alert_service.notifications.messages) == 1
    assert len(await alert_service.maintenance.list_incidents(active_only=True)) == 1


@pytest.mark.asyncio
async def test_delivery_failure_keeps_alert_open_and_retries_without_duplicate_alert(alert_service):
    class _RetryingNotifications:
        def __init__(self):
            self.calls = 0

        async def notify_admins(self, text):
            self.calls += 1
            return {
                "attempted": 1,
                "delivered": 0 if self.calls == 1 else 1,
                "results": [{"delivered": self.calls > 1}],
            }

    alert_service.notifications = _RetryingNotifications()
    first = await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Transient outage."
    )
    second = await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Transient outage."
    )
    assert first["alert"]["status"] == AlertStatus.OPEN.value
    assert first["notification"]["delivered"] == 0
    assert second["notification"]["delivered"] == 1
    assert second["alert"]["public_id"] == first["alert"]["public_id"]
    assert len(await alert_service.maintenance.list_incidents(active_only=True)) == 1


@pytest.mark.asyncio
async def test_operations_snapshot_reports_real_alert_and_maintenance_state(alert_service):
    from app.services.health_service import HealthService
    from app.services.production_operations_service import ProductionOperationsService

    class _Scheduler:
        class _Inner:
            running = True

        _scheduler = _Inner()

    await alert_service.evaluate_component(
        component="outline_apis", healthy=False, safe_summary="Provider unavailable."
    )
    health = HealthService(db=alert_service.db, scheduler=_Scheduler())
    operations = ProductionOperationsService(
        health_service=health,
        scheduler=_Scheduler(),
        maintenance_service=alert_service.maintenance,
        alert_service=alert_service,
    )
    snapshot = await operations.get_operations_snapshot()
    assert snapshot.alerts["available"] is True
    assert snapshot.alerts["open_count"] == 1
    assert snapshot.incidents["active_count"] == 1
    assert snapshot.maintenance["active_count"] == 1


@pytest.mark.asyncio
async def test_controlled_full_flow_produces_evidence_backed_readiness_verdict(alert_service):
    from app.lifecycle import AppState, LifecycleManager
    from app.services.production_operations_service import (
        ProductionOperationsService,
        ReadinessVerdict,
    )

    class _Scheduler:
        class _Inner:
            running = True

        _scheduler = _Inner()

    provider = {"healthy": True}
    health = HealthService(db=alert_service.db, scheduler=_Scheduler())
    health.set_provider_probe(
        "outline_apis",
        lambda checked_at: OperationalHealthStatus.HEALTHY
        if provider["healthy"]
        else OperationalHealthStatus.UNHEALTHY,
    )
    lifecycle = LifecycleManager()
    lifecycle.set_state(AppState.RUNNING)

    healthy_before = await health.check_system()
    healthy_result = next(
        item for item in healthy_before.components if item.component == "outline_apis"
    )
    provider["healthy"] = False
    failed = await health.check_system()
    failed_result = next(item for item in failed.components if item.component == "outline_apis")
    opened = await alert_service.evaluate_health_result(failed_result)
    notice_en = await alert_service.maintenance.get_customer_notice(
        "vpn_provisioning", language="en"
    )
    notice_my = await alert_service.maintenance.get_customer_notice(
        "vpn_provisioning", language="my"
    )

    provider["healthy"] = True
    recovered = await health.check_system()
    recovered_result = next(
        item for item in recovered.components if item.component == "outline_apis"
    )
    recovery = await alert_service.recover_component(
        component="outline_apis", now=recovered_result.checked_at
    )
    active_incidents = await alert_service.maintenance.list_incidents(active_only=True)
    snapshot_service = ProductionOperationsService(
        health_service=health,
        scheduler=_Scheduler(),
        maintenance_service=alert_service.maintenance,
        alert_service=alert_service,
        backup_service=type("Backups", (), {"list_backups": _async_verified_backups})(),
        lifecycle_manager=lifecycle,
    )
    snapshot = await snapshot_service.get_operations_snapshot()
    evidence = {
        "health_detected": failed_result.status == OperationalHealthStatus.UNHEALTHY,
        "alert_opened": opened["alert"]["status"] == AlertStatus.OPEN.value,
        "incident_opened": opened["alert"]["incident_id"] is not None,
        "maintenance_started": opened["maintenance_window"]["status"] == "active",
        "customer_notified": bool(notice_en and notice_my),
        "provider_recovered": recovered_result.status == OperationalHealthStatus.HEALTHY,
        "recovery_checked": recovery["recovery_check"]["healthy"] is True,
        "maintenance_ended": recovery["maintenance_end"]["ended"] is True,
        "alert_resolved": recovery["alert"]["status"] == AlertStatus.RESOLVED.value,
        "incident_resolved": active_incidents == [],
    }
    assert all(evidence.values())
    assert healthy_result.status == OperationalHealthStatus.HEALTHY
    assert snapshot.alerts["available"] is True
    assert snapshot.alerts["open_count"] == 0
    assert snapshot.maintenance["active_count"] == 0
    assert snapshot.incidents["active_count"] == 0
    report = await snapshot_service.evaluate_readiness(
        tests_executed=True,
        test_evidence={"suite": "phase0-7.6", "passed": 1},
        flow_evidence=evidence,
    )
    assert report.verdict in {ReadinessVerdict.READY, ReadinessVerdict.READY_WITH_WARNINGS}
    assert not any(
        reason.startswith("end_to_end_flow_evidence_missing") for reason in report.blocking_reasons
    )


async def _async_verified_backups(self, **kwargs):
    return [{"status": "verified", "restore_test_status": "passed"}]
