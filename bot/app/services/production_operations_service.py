"""Phase 7.6 production-operations orchestration and readiness evidence gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.lifecycle import AppState, lifecycle
from app.services.health_service import HealthService, OperationalHealthStatus
from app.services.maintenance_service import MaintenanceService, MaintenanceState
from app.utils.startup_checks import StartupError, run_all_checks
from database.models.background_job import BackgroundJobStatus


class ReadinessVerdict(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class OperationsStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProductionOperationsSnapshot:
    generated_at: datetime
    overall_status: OperationsStatus
    system_health: dict[str, Any]
    workers: dict[str, Any]
    scheduler: dict[str, Any]
    jobs: dict[str, Any]
    backups: dict[str, Any]
    maintenance: dict[str, Any]
    incidents: dict[str, Any]
    configuration: dict[str, Any]
    lifecycle: dict[str, Any]
    alerts: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProductionReadinessReport:
    verdict: ReadinessVerdict
    generated_at: datetime
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    snapshot: ProductionOperationsSnapshot | None = None


class ProductionOperationsService:
    """Thin aggregator; subsystem services remain the source of truth."""

    def __init__(
        self,
        *,
        health_service: HealthService,
        job_service: Any = None,
        scheduler: Any = None,
        backup_service: Any = None,
        maintenance_service: MaintenanceService | None = None,
        alert_service: Any = None,
        settings: Any = None,
        lifecycle_manager: Any = None,
    ) -> None:
        self.health = health_service
        self.jobs = job_service
        self.scheduler = scheduler
        self.backups = backup_service
        self.maintenance = maintenance_service
        self.alerts = alert_service
        self.settings = settings
        self.lifecycle = lifecycle_manager or lifecycle

    @staticmethod
    def _job_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            status = str(row.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _health_status(snapshot: Any) -> OperationsStatus:
        value = snapshot.overall.value
        if value == OperationalHealthStatus.UNHEALTHY.value:
            return OperationsStatus.UNHEALTHY
        if value in {
            OperationalHealthStatus.DEGRADED.value,
            OperationalHealthStatus.UNKNOWN.value,
            OperationalHealthStatus.STALE.value,
        }:
            return OperationsStatus.DEGRADED
        return OperationsStatus.HEALTHY

    async def get_operations_snapshot(self) -> ProductionOperationsSnapshot:
        now = datetime.now(UTC)
        health = await self.health.check_system()
        job_rows = await self.jobs.list_jobs(limit=500) if self.jobs is not None else []
        backup_rows = await self.backups.list_backups(limit=100) if self.backups is not None else []
        active_windows = (
            await self.maintenance.list_windows(active_only=True)
            if self.maintenance is not None
            else []
        )
        incidents = (
            await self.maintenance.list_incidents(active_only=True)
            if self.maintenance is not None
            else []
        )
        open_alerts = await self.alerts.list_open(limit=100) if self.alerts is not None else []
        evaluator_available = self.alerts is not None
        notification_available = (
            evaluator_available and getattr(self.alerts, "notifications", None) is not None
        )
        scheduler_running = bool(
            self.scheduler is not None
            and getattr(getattr(self.scheduler, "_scheduler", None), "running", False)
        )
        maintenance_states = {str(row.get("state")) for row in active_windows}
        status = self._health_status(health)
        if MaintenanceState.EMERGENCY.value in maintenance_states:
            status = OperationsStatus.EMERGENCY
        elif active_windows and status in {OperationsStatus.HEALTHY, OperationsStatus.DEGRADED}:
            status = (
                OperationsStatus.MAINTENANCE
                if any(
                    str(row.get("state"))
                    in {MaintenanceState.MAINTENANCE.value, MaintenanceState.READ_ONLY.value}
                    for row in active_windows
                )
                else OperationsStatus.DEGRADED
            )
        job_counts = self._job_counts(job_rows)
        failed = sum(
            job_counts.get(key, 0)
            for key in (BackgroundJobStatus.FAILED.value, BackgroundJobStatus.DEAD_LETTER.value)
        )
        latest_backup = backup_rows[0] if backup_rows else None
        return ProductionOperationsSnapshot(
            generated_at=now,
            overall_status=status,
            system_health={
                "overall": health.overall.value,
                "components": [
                    {
                        "component": c.component,
                        "status": c.status.value,
                        "critical": c.critical,
                        "error_code": c.error_code,
                    }
                    for c in health.components
                ],
                "failed_jobs": health.failed_jobs,
                "stale_operations": health.stale_operations,
                "capacity": health.capacity,
            },
            workers={
                "status": "HEALTHY" if scheduler_running else "UNHEALTHY",
                "scheduler_backed": scheduler_running,
            },
            scheduler={"running": scheduler_running},
            jobs={"total": len(job_rows), "counts": job_counts, "failed_or_dead_letter": failed},
            backups={
                "count": len(backup_rows),
                "latest": latest_backup,
                "verified_count": sum(row.get("status") == "verified" for row in backup_rows),
                "restore_tested_count": sum(
                    row.get("restore_test_status") == "passed" for row in backup_rows
                ),
            },
            maintenance={"active_count": len(active_windows), "windows": active_windows},
            incidents={"active_count": len(incidents), "incidents": incidents},
            configuration={
                "injected": self.settings is not None,
                "environment": getattr(self.settings, "environment", None),
            },
            lifecycle={
                "state": self.lifecycle.state.value,
                "ready": self.lifecycle.is_ready(),
                "stopping": self.lifecycle.is_stopping(),
            },
            alerts={
                "available": evaluator_available and notification_available,
                "evaluator_available": evaluator_available,
                "notification_available": notification_available,
                "open_count": len(open_alerts),
                "alerts": open_alerts,
                "reason": None
                if evaluator_available and notification_available
                else (
                    "alert_evaluator_not_available"
                    if not evaluator_available
                    else "notification_delivery_not_available"
                ),
            },
        )

    async def evaluate_startup_readiness(self) -> dict[str, Any]:
        """Reuse boot preflight as structured evidence; never swallow a critical failure."""
        try:
            await run_all_checks(
                self.settings,
                db=getattr(self.health, "_db", None),
                scheduler=self.scheduler,
                cache_service=getattr(self.health, "_cache", None),
            )
            return {"ready": True, "error": None}
        except StartupError as exc:
            return {"ready": False, "error": str(exc).replace("BOT_TOKEN", "BOT_TOKEN_REDACTED")}
        except Exception:
            return {"ready": False, "error": "startup_check_failed"}

    def evaluate_liveness(self) -> dict[str, Any]:
        return {"live": not self.lifecycle.is_stopping(), "state": self.lifecycle.state.value}

    def evaluate_shutdown_state(self) -> dict[str, Any]:
        return {
            "safe_to_shutdown": self.lifecycle.state in {AppState.STOPPING, AppState.STOPPED},
            "state": self.lifecycle.state.value,
        }

    async def evaluate_readiness(  # noqa: PLR0912
        self,
        *,
        tests_executed: bool = False,
        test_evidence: dict[str, Any] | None = None,
        flow_evidence: dict[str, Any] | None = None,
    ) -> ProductionReadinessReport:
        snapshot = await self.get_operations_snapshot()
        blocking: list[str] = []
        warnings: list[str] = []
        if not tests_executed:
            blocking.append("test_evidence_missing")
        required_flow = (
            "health_detected",
            "alert_opened",
            "incident_opened",
            "maintenance_started",
            "customer_notified",
            "provider_recovered",
            "recovery_checked",
            "maintenance_ended",
            "alert_resolved",
            "incident_resolved",
        )
        missing_flow = [key for key in required_flow if not (flow_evidence or {}).get(key)]
        if missing_flow:
            blocking.append("end_to_end_flow_evidence_missing:" + ",".join(missing_flow))
        if snapshot.system_health["overall"] == OperationalHealthStatus.UNHEALTHY.value:
            blocking.append("critical_health_unhealthy")
        if not snapshot.scheduler["running"]:
            blocking.append("scheduler_not_running")
        if snapshot.lifecycle["state"] in {
            AppState.STARTING.value,
            AppState.STOPPING.value,
            AppState.STOPPED.value,
        }:
            blocking.append(f"lifecycle_{snapshot.lifecycle['state']}")
        if snapshot.jobs["failed_or_dead_letter"]:
            warnings.append("failed_or_dead_letter_jobs_present")
        if snapshot.alerts["available"] is False:
            blocking.append(snapshot.alerts["reason"] or "alert_evaluator_not_available")
        if snapshot.backups["count"] == 0:
            warnings.append("no_backup_evidence")
        elif snapshot.backups["verified_count"] == 0:
            warnings.append("no_verified_backup_evidence")
        if snapshot.incidents["active_count"]:
            warnings.append("active_incidents_present")
        if snapshot.overall_status in {OperationsStatus.EMERGENCY, OperationsStatus.UNHEALTHY}:
            blocking.append(f"overall_{snapshot.overall_status.value.lower()}")
        if blocking:
            verdict = ReadinessVerdict.NOT_READY
        elif warnings:
            verdict = ReadinessVerdict.READY_WITH_WARNINGS
        else:
            verdict = ReadinessVerdict.READY
        return ProductionReadinessReport(
            verdict,
            snapshot.generated_at,
            tuple(blocking),
            tuple(warnings),
            {
                "tests": test_evidence or {"executed": tests_executed},
                "flow": flow_evidence or {},
                "required_flow": required_flow,
            },
            snapshot,
        )
