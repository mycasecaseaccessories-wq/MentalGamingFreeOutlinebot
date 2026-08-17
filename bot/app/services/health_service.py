"""
HealthService — application health reporting.

Aggregates the status of all critical subsystems into a single
HealthReport.  Used by the admin health-check command (Phase 2) and
can be exposed via a future HTTP /healthz endpoint.

Subsystems monitored
--------------------
database   — Can the DB accept a query?
bot        — Is the Telegram bot connected?
scheduler  — Is APScheduler running?
config     — Are critical settings present?

Future (Phase 3+):
  outline_servers — Can we reach registered Outline API endpoints?

Phase 0.5: Full implementation of architecture; no business logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from datetime import datetime, timedelta, timezone
from time import perf_counter

from sqlalchemy import func, select

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class OperationalHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"
    STALE = "stale"


class HealthStatus(str, Enum):
    """Overall health level for a subsystem or the whole application."""
    OK       = "ok"
    DEGRADED = "degraded"
    DOWN     = "down"
    UNKNOWN  = "unknown"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SubsystemHealth:
    """
    Health report for a single subsystem.

    Attributes:
        name:    Human-readable subsystem name.
        status:  Current HealthStatus.
        message: Optional detail message (error text, latency, etc.).
    """
    name:    str
    status:  HealthStatus
    message: Optional[str] = None

    def is_healthy(self) -> bool:
        """Return True when the subsystem is fully operational."""
        return self.status == HealthStatus.OK

    def __str__(self) -> str:
        icon = {"ok": "✅", "degraded": "⚠️", "down": "❌", "unknown": "❓"}.get(
            self.status.value, "❓"
        )
        detail = f" — {self.message}" if self.message else ""
        return f"{icon} {self.name}{detail}"


@dataclass
class HealthReport:
    """
    Aggregated health report for the entire application.

    Attributes:
        overall:     Worst-case status across all subsystems.
        subsystems:  Individual subsystem reports.
    """
    overall:    HealthStatus = HealthStatus.UNKNOWN
    subsystems: list[SubsystemHealth] = field(default_factory=list)

    def is_healthy(self) -> bool:
        """Return True only when all subsystems are OK."""
        return self.overall == HealthStatus.OK

    def add(self, sub: SubsystemHealth) -> None:
        """Register a subsystem report and update the overall status."""
        self.subsystems.append(sub)
        self._recalculate_overall()

    def _recalculate_overall(self) -> None:
        if any(s.status == HealthStatus.DOWN for s in self.subsystems):
            self.overall = HealthStatus.DOWN
        elif any(s.status in (HealthStatus.DEGRADED, HealthStatus.UNKNOWN) for s in self.subsystems):
            self.overall = HealthStatus.DEGRADED
        elif all(s.status == HealthStatus.OK for s in self.subsystems):
            self.overall = HealthStatus.OK
        else:
            self.overall = HealthStatus.UNKNOWN

    def format(self) -> str:
        """Return a multi-line text summary suitable for a Telegram message."""
        icon = {"ok": "✅", "degraded": "⚠️", "down": "❌", "unknown": "❓"}.get(
            self.overall.value, "❓"
        )
        lines = [f"<b>System Health: {icon} {self.overall.value.upper()}</b>", ""]
        for sub in self.subsystems:
            lines.append(str(sub))
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    component: str
    status: OperationalHealthStatus
    checked_at: datetime
    latency_ms: int | None = None
    message_code: str | None = None
    safe_details: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    fresh_until: datetime | None = None
    critical: bool = False


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    overall: OperationalHealthStatus
    checked_at: datetime
    components: tuple[HealthCheckResult, ...]
    failed_jobs: int = 0
    stale_operations: int = 0
    capacity: dict[str, int | float | None] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HealthService
# ---------------------------------------------------------------------------

class HealthService:
    """
    Checks and reports the health of all application subsystems.

    Usage:
        svc = HealthService(db=db, scheduler=scheduler)
        report = await svc.check_all()
        if not report.is_healthy():
            logger.warning("Degraded: %s", report.format())
    """

    def __init__(
        self,
        db=None,
        scheduler=None,
        bot=None,
        settings=None,
        cache=None,
    ) -> None:
        """
        Args:
            db:        DatabaseManager instance (optional).
            scheduler: Scheduler instance (optional).
            bot:       telegram.Bot instance (optional, available post-init).
            settings:  Application Settings instance (optional).
            cache:     CacheService instance (optional).
        """
        self._db        = db
        self._scheduler = scheduler
        self._bot       = bot
        self._settings  = settings
        self._cache     = cache
        self._registry  = None
        self._latest_snapshot: HealthSnapshot | None = None
        self._freshness_seconds = 300

    def set_registry(self, registry) -> None:
        """Attach ServiceRegistry after initialization for optional adapters."""
        self._registry = registry

    def get_latest_snapshot(self) -> HealthSnapshot | None:
        return self._latest_snapshot

    # ── Individual checks ─────────────────────────────────────────────────

    async def check_database(self) -> SubsystemHealth:
        """Verify database connectivity with a lightweight query."""
        if self._db is None:
            return SubsystemHealth("Database", HealthStatus.UNKNOWN, "not injected")
        try:
            from sqlalchemy import text
            async with self._db.session() as session:
                await session.execute(text("SELECT 1"))
            return SubsystemHealth("Database", HealthStatus.OK)
        except Exception as exc:
            logger.error("Health check — database DOWN: %s", exc)
            return SubsystemHealth("Database", HealthStatus.DOWN, str(exc))

    async def check_bot(self) -> SubsystemHealth:
        """Verify the Telegram bot is connected by calling getMe()."""
        if self._bot is None:
            return SubsystemHealth("Telegram Bot", HealthStatus.UNKNOWN, "not injected")
        try:
            me = await self._bot.get_me()
            return SubsystemHealth("Telegram Bot", HealthStatus.OK, f"@{me.username}")
        except Exception as exc:
            logger.error("Health check — bot DOWN: %s", exc)
            return SubsystemHealth("Telegram Bot", HealthStatus.DOWN, str(exc))

    def check_scheduler(self) -> SubsystemHealth:
        """Verify the background scheduler is running."""
        if self._scheduler is None:
            return SubsystemHealth("Scheduler", HealthStatus.UNKNOWN, "not injected")
        try:
            is_running = (
                self._scheduler._scheduler is not None
                and self._scheduler._scheduler.running
            )
            if is_running:
                return SubsystemHealth("Scheduler", HealthStatus.OK)
            return SubsystemHealth("Scheduler", HealthStatus.DEGRADED, "not running")
        except Exception as exc:
            return SubsystemHealth("Scheduler", HealthStatus.UNKNOWN, str(exc))

    def check_configuration(self) -> SubsystemHealth:
        """Verify critical configuration values are present."""
        if self._settings is None:
            return SubsystemHealth("Configuration", HealthStatus.UNKNOWN, "not injected")
        try:
            issues: list[str] = []
            if not getattr(self._settings, "bot_token", ""):
                issues.append("BOT_TOKEN missing")
            if not getattr(self._settings, "database_url", ""):
                issues.append("DATABASE_URL missing")
            if issues:
                return SubsystemHealth(
                    "Configuration", HealthStatus.DOWN, "; ".join(issues)
                )
            return SubsystemHealth(
                "Configuration", HealthStatus.OK,
                f"env={self._settings.environment}"
            )
        except Exception as exc:
            return SubsystemHealth("Configuration", HealthStatus.UNKNOWN, str(exc))

    def check_cache(self) -> SubsystemHealth:
        """Verify the cache service is initialised."""
        if self._cache is None:
            return SubsystemHealth("Cache", HealthStatus.UNKNOWN, "not injected")
        try:
            backend = type(self._cache._backend).__name__
            return SubsystemHealth("Cache", HealthStatus.OK, f"backend={backend}")
        except Exception as exc:
            return SubsystemHealth("Cache", HealthStatus.UNKNOWN, str(exc))

    def check_localization(self) -> SubsystemHealth:
        """Verify that at least one locale can be loaded."""
        try:
            from locales.translator import _get_registry
            registry = _get_registry()
            loaded = [lang for lang in ("en", "my") if registry.get(lang)]
            if not loaded:
                return SubsystemHealth(
                    "Localisation", HealthStatus.DOWN, "no locales loaded"
                )
            return SubsystemHealth(
                "Localisation", HealthStatus.OK,
                f"langs={loaded}",
            )
        except Exception as exc:
            logger.error("Health check — localization DOWN: %s", exc)
            return SubsystemHealth("Localisation", HealthStatus.DOWN, str(exc))

    # ── Composite check ───────────────────────────────────────────────────

    async def check_all(self) -> HealthReport:
        """
        Run all health checks and return a HealthReport.

        Returns:
            HealthReport with overall status and per-subsystem details.
        """
        report = HealthReport()
        report.add(self.check_configuration())
        report.add(self.check_localization())
        report.add(await self.check_database())
        report.add(self.check_scheduler())
        report.add(self.check_cache())
        # Bot check is last as it makes a network call.
        report.add(await self.check_bot())

        logger.info(
            "Health check complete — overall=%s subsystems=%d",
            report.overall.value, len(report.subsystems),
        )
        return report

    async def check_system(self) -> HealthSnapshot:
        """Run the Phase 7.1 read-only operational snapshot."""
        checked_at = datetime.now(timezone.utc)
        components = await self._check_components(checked_at)
        failed_jobs = 0
        stale_operations = 0
        capacity: dict[str, int | float | None] = {}
        if self._db is not None:
            failed_jobs, stale_operations, capacity = await self._operational_counts(checked_at)
        overall = self._derive_overall(components)
        snapshot = HealthSnapshot(overall, checked_at, tuple(components), failed_jobs, stale_operations, capacity)
        self._latest_snapshot = snapshot
        return snapshot

    async def check_database_snapshot(self, checked_at: datetime | None = None) -> HealthCheckResult:
        checked_at = checked_at or datetime.now(timezone.utc)
        if self._db is None:
            return HealthCheckResult("database", OperationalHealthStatus.UNKNOWN, checked_at, message_code="dependency_not_injected", critical=True)
        started = perf_counter()
        try:
            from sqlalchemy import text
            async with self._db.session() as session:
                await session.execute(text("SELECT 1"))
            latency = int((perf_counter() - started) * 1000)
            status = OperationalHealthStatus.HEALTHY if latency < 1500 else OperationalHealthStatus.DEGRADED
            return HealthCheckResult("database", status, checked_at, latency_ms=latency, message_code="reachable", critical=True, fresh_until=checked_at + timedelta(seconds=self._freshness_seconds))
        except Exception:
            latency = int((perf_counter() - started) * 1000)
            return HealthCheckResult("database", OperationalHealthStatus.UNHEALTHY, checked_at, latency_ms=latency, message_code="query_failed", error_code="database_unreachable", critical=True)

    async def check_bot_snapshot(self, checked_at: datetime | None = None) -> HealthCheckResult:
        checked_at = checked_at or datetime.now(timezone.utc)
        if self._bot is None:
            return HealthCheckResult("bot", OperationalHealthStatus.UNKNOWN, checked_at, message_code="dependency_not_injected", critical=True)
        started = perf_counter()
        try:
            await self._bot.get_me()
            latency = int((perf_counter() - started) * 1000)
            status = OperationalHealthStatus.HEALTHY if latency < 3000 else OperationalHealthStatus.DEGRADED
            return HealthCheckResult("bot", status, checked_at, latency_ms=latency, message_code="telegram_reachable", critical=True, fresh_until=checked_at + timedelta(seconds=self._freshness_seconds))
        except Exception:
            return HealthCheckResult("bot", OperationalHealthStatus.UNHEALTHY, checked_at, message_code="telegram_unreachable", error_code="bot_unreachable", critical=True)

    def check_worker_snapshot(self, checked_at: datetime | None = None) -> HealthCheckResult:
        checked_at = checked_at or datetime.now(timezone.utc)
        if self._scheduler is None:
            return HealthCheckResult("workers", OperationalHealthStatus.UNKNOWN, checked_at, message_code="worker_probe_unavailable", critical=False)
        try:
            running = self._scheduler._scheduler is not None and self._scheduler._scheduler.running
            return HealthCheckResult("workers", OperationalHealthStatus.HEALTHY if running else OperationalHealthStatus.UNHEALTHY, checked_at, message_code="running" if running else "not_running", critical=True, fresh_until=checked_at + timedelta(seconds=self._freshness_seconds))
        except Exception:
            return HealthCheckResult("workers", OperationalHealthStatus.UNKNOWN, checked_at, message_code="worker_probe_failed", error_code="worker_probe_failed", critical=False)

    async def check_server_snapshot(self, checked_at: datetime | None = None) -> HealthCheckResult:
        checked_at = checked_at or datetime.now(timezone.utc)
        if self._db is None:
            return HealthCheckResult("vpn_servers", OperationalHealthStatus.UNKNOWN, checked_at, message_code="dependency_not_injected")
        try:
            from database.models.server import ServerORM
            async with self._db.session() as session:
                rows = list((await session.execute(select(ServerORM).where(ServerORM.archived_at.is_(None)))).scalars().all())
            total = len(rows)
            healthy = sum(1 for row in rows if row.health_status in {"healthy", "ok"} and not row.stale_data and row.status == "online")
            unhealthy = sum(1 for row in rows if row.health_status in {"unhealthy", "offline"} or row.status == "offline")
            stale = sum(1 for row in rows if row.stale_data)
            if total == 0:
                status = OperationalHealthStatus.UNKNOWN
            elif healthy == total:
                status = OperationalHealthStatus.HEALTHY
            elif unhealthy or stale:
                status = OperationalHealthStatus.DEGRADED
            else:
                status = OperationalHealthStatus.DEGRADED
            return HealthCheckResult("vpn_servers", status, checked_at, message_code="server_registry_summary", safe_details={"total": total, "healthy": healthy, "unhealthy": unhealthy, "stale": stale}, critical=False, fresh_until=checked_at + timedelta(seconds=self._freshness_seconds))
        except Exception:
            return HealthCheckResult("vpn_servers", OperationalHealthStatus.UNKNOWN, checked_at, message_code="server_summary_failed", error_code="server_summary_failed")

    def check_provider_snapshot(self, component: str, *, checked_at: datetime | None = None) -> HealthCheckResult:
        checked_at = checked_at or datetime.now(timezone.utc)
        return HealthCheckResult(component, OperationalHealthStatus.UNKNOWN, checked_at, message_code="provider_probe_unavailable", safe_details={"supported": False}, critical=False)

    async def _check_components(self, checked_at: datetime) -> list[HealthCheckResult]:
        db_result, bot_result, server_result = await self.check_database_snapshot(checked_at), await self.check_bot_snapshot(checked_at), await self.check_server_snapshot(checked_at)
        return [db_result, bot_result, self.check_worker_snapshot(checked_at), server_result, self.check_provider_snapshot("outline_apis", checked_at=checked_at), self.check_provider_snapshot("payments", checked_at=checked_at), self.check_provider_snapshot("notifications", checked_at=checked_at)]

    async def _operational_counts(self, checked_at: datetime) -> tuple[int, int, dict[str, int | float | None]]:
        from database.models.server import ServerORM
        from database.models.vpn_provisioning_operation import VPNProvisioningOperationORM
        stale_cutoff = checked_at - timedelta(seconds=self._freshness_seconds * 3)
        try:
            async with self._db.session() as session:
                failed = int(await session.scalar(select(func.count(VPNProvisioningOperationORM.id)).where(VPNProvisioningOperationORM.status.in_([VPNProvisioningOperationORM.STATUS_FAILED, VPNProvisioningOperationORM.STATUS_COMPENSATION_REQUIRED]))) or 0)
                stale = int(await session.scalar(select(func.count(VPNProvisioningOperationORM.id)).where(VPNProvisioningOperationORM.status.in_([VPNProvisioningOperationORM.STATUS_PENDING, VPNProvisioningOperationORM.STATUS_SELECTING_SERVER, VPNProvisioningOperationORM.STATUS_RESERVED, VPNProvisioningOperationORM.STATUS_CREATING_REMOTE_KEY, VPNProvisioningOperationORM.STATUS_PERSISTING_LOCAL_KEY])).where(VPNProvisioningOperationORM.updated_at <= stale_cutoff)) or 0)
                rows = list((await session.execute(select(ServerORM).where(ServerORM.archived_at.is_(None)))).scalars().all())
            total_users = sum(max(0, int(row.max_users or 0)) for row in rows if row.max_users is not None)
            used_users = sum(max(0, int(row.current_users or 0)) for row in rows)
            total_keys = sum(max(0, int(row.max_keys or 0)) for row in rows if row.max_keys is not None)
            used_keys = sum(max(0, int(row.existing_key_count or 0)) for row in rows)
            return failed, stale, {"servers": len(rows), "max_users": total_users or None, "current_users": used_users, "max_keys": total_keys or None, "existing_keys": used_keys, "user_utilization_percent": round((used_users / total_users) * 100, 2) if total_users else None, "key_utilization_percent": round((used_keys / total_keys) * 100, 2) if total_keys else None}
        except Exception:
            return 0, 0, {"servers": None, "max_users": None, "current_users": None, "max_keys": None, "existing_keys": None, "user_utilization_percent": None, "key_utilization_percent": None}

    @staticmethod
    def _derive_overall(components: list[HealthCheckResult]) -> OperationalHealthStatus:
        critical = [component for component in components if component.critical]
        all_components = critical or components
        if any(component.status == OperationalHealthStatus.UNHEALTHY for component in all_components):
            return OperationalHealthStatus.UNHEALTHY
        if any(component.status in {OperationalHealthStatus.DEGRADED, OperationalHealthStatus.STALE, OperationalHealthStatus.UNKNOWN} for component in all_components):
            return OperationalHealthStatus.DEGRADED
        return OperationalHealthStatus.HEALTHY

    async def is_healthy(self) -> bool:
        """Return True only when all subsystems are OK."""
        report = await self.check_all()
        return report.is_healthy()
