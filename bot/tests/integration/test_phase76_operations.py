import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.lifecycle import AppState, LifecycleManager
from app.services.health_service import HealthCheckResult, OperationalHealthStatus
from app.services.production_operations_service import (
    OperationsStatus,
    ProductionOperationsService,
    ReadinessVerdict,
)


class _Health:
    def __init__(self, overall=OperationalHealthStatus.HEALTHY):
        self.overall = overall

    async def check_system(self):
        now = datetime.now(UTC)
        return type(
            "Snapshot",
            (),
            {
                "overall": self.overall,
                "components": (HealthCheckResult("database", self.overall, now, critical=True),),
                "failed_jobs": 0,
                "stale_operations": 0,
                "capacity": {},
            },
        )()


class _Jobs:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def list_jobs(self, **kwargs):
        return self.rows


class _Backups:
    async def list_backups(self, **kwargs):
        return [{"status": "verified", "restore_test_status": "passed"}]


class _Maintenance:
    async def list_windows(self, **kwargs):
        return []

    async def list_incidents(self, **kwargs):
        return []


class _Scheduler:
    class _Inner:
        running = True

    _scheduler = _Inner()


def _service(health=None, jobs=None, lifecycle_manager=None):
    return ProductionOperationsService(
        health_service=health or _Health(),
        job_service=jobs or _Jobs(),
        scheduler=_Scheduler(),
        backup_service=_Backups(),
        maintenance_service=_Maintenance(),
        settings=type("Settings", (), {"environment": "test"})(),
        lifecycle_manager=lifecycle_manager or _running_lifecycle(),
    )


def _running_lifecycle():
    manager = LifecycleManager()
    manager.set_state(AppState.RUNNING)
    return manager


@pytest.mark.asyncio
async def test_phase76_never_declares_ready_without_test_evidence():
    report = await _service().evaluate_readiness(tests_executed=False)
    assert report.verdict == ReadinessVerdict.NOT_READY
    assert "test_evidence_missing" in report.blocking_reasons


@pytest.mark.asyncio
async def test_phase76_missing_flow_and_alert_evidence_is_not_ready():
    report = await _service().evaluate_readiness(
        tests_executed=True, test_evidence={"suite": "phase0-7.6", "passed": 1}
    )
    assert report.verdict == ReadinessVerdict.NOT_READY
    assert "alert_evaluator_not_available" in report.blocking_reasons
    assert any(
        item.startswith("end_to_end_flow_evidence_missing:") for item in report.blocking_reasons
    )
    assert report.snapshot.overall_status == OperationsStatus.HEALTHY


@pytest.mark.asyncio
async def test_phase76_failure_injection_blocks_readiness():
    report = await _service(health=_Health(OperationalHealthStatus.UNHEALTHY)).evaluate_readiness(
        tests_executed=True, flow_evidence={"health_detected": True}
    )
    assert report.verdict == ReadinessVerdict.NOT_READY
    assert "critical_health_unhealthy" in report.blocking_reasons
    assert "overall_unhealthy" in report.blocking_reasons


@pytest.mark.asyncio
async def test_phase76_dead_letter_jobs_are_additional_blocking_evidence_gap():
    report = await _service(jobs=_Jobs([{"status": "dead_letter"}])).evaluate_readiness(
        tests_executed=True, flow_evidence={"health_detected": True}
    )
    assert report.verdict == ReadinessVerdict.NOT_READY
    assert "failed_or_dead_letter_jobs_present" in report.warnings


@pytest.mark.asyncio
async def test_phase76_stopping_lifecycle_blocks_readiness():
    manager = LifecycleManager()
    manager.set_state(AppState.STOPPING)
    report = await _service(lifecycle_manager=manager).evaluate_readiness(
        tests_executed=True, flow_evidence={"health_detected": True}
    )
    assert report.verdict == ReadinessVerdict.NOT_READY
    assert "lifecycle_stopping" in report.blocking_reasons
