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
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

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
    ) -> None:
        """
        Args:
            db:        DatabaseManager instance (optional).
            scheduler: Scheduler instance (optional).
            bot:       telegram.Bot instance (optional, available post-init).
            settings:  Application Settings instance (optional).
        """
        self._db        = db
        self._scheduler = scheduler
        self._bot       = bot
        self._settings  = settings

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

    # ── Composite check ───────────────────────────────────────────────────

    async def check_all(self) -> HealthReport:
        """
        Run all health checks and return a HealthReport.

        Returns:
            HealthReport with overall status and per-subsystem details.
        """
        report = HealthReport()
        report.add(self.check_configuration())
        report.add(await self.check_database())
        report.add(self.check_scheduler())
        # Bot check is last as it makes a network call.
        report.add(await self.check_bot())

        logger.info(
            "Health check complete — overall=%s subsystems=%d",
            report.overall.value, len(report.subsystems),
        )
        return report

    async def is_healthy(self) -> bool:
        """Return True only when all subsystems are OK."""
        report = await self.check_all()
        return report.is_healthy()
