from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.health_service import (
    HealthCheckResult,
    HealthService,
    OperationalHealthStatus,
)


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query):
        return object()


class _DB:
    def session(self):
        return _Session()


class _BrokenSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query):
        raise RuntimeError("secret://database-password should never be returned")


class _BrokenDB:
    def session(self):
        return _BrokenSession()


def _result(component: str, status: OperationalHealthStatus, critical: bool = False):
    return HealthCheckResult(component, status, datetime.now(timezone.utc), critical=critical)


def test_phase71_overall_health_is_derived_from_components():
    assert HealthService._derive_overall([_result("database", OperationalHealthStatus.HEALTHY, True)]) == OperationalHealthStatus.HEALTHY
    assert HealthService._derive_overall([_result("database", OperationalHealthStatus.DEGRADED, True)]) == OperationalHealthStatus.DEGRADED
    assert HealthService._derive_overall([_result("database", OperationalHealthStatus.UNHEALTHY, True)]) == OperationalHealthStatus.UNHEALTHY
    assert HealthService._derive_overall([_result("payments", OperationalHealthStatus.UNKNOWN)]) == OperationalHealthStatus.DEGRADED


@pytest.mark.asyncio
async def test_phase71_database_check_is_lightweight_and_timed():
    result = await HealthService(db=_DB()).check_database_snapshot()
    assert result.component == "database"
    assert result.status in {OperationalHealthStatus.HEALTHY, OperationalHealthStatus.DEGRADED}
    assert result.latency_ms is not None
    assert result.error_code is None


@pytest.mark.asyncio
async def test_phase71_database_failure_redacts_exception_text():
    result = await HealthService(db=_BrokenDB()).check_database_snapshot()
    assert result.status == OperationalHealthStatus.UNHEALTHY
    assert result.error_code == "database_unreachable"
    assert result.message_code == "query_failed"
    assert "secret://" not in str(result)


def test_phase71_unsupported_provider_is_explicitly_unknown():
    result = HealthService().check_provider_snapshot("payments")
    assert result.status == OperationalHealthStatus.UNKNOWN
    assert result.message_code == "provider_probe_unavailable"
    assert result.safe_details == {"supported": False}


def test_phase71_status_enum_is_bounded():
    assert {item.value for item in OperationalHealthStatus} == {"healthy", "degraded", "unhealthy", "unknown", "disabled", "stale"}
