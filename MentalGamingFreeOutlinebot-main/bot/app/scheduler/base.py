"""
Scheduler wrapper.

Wraps APScheduler's AsyncIOScheduler to provide a clean interface for
registering and managing background jobs.

Usage in main.py:
    from app.scheduler import Scheduler
    scheduler = Scheduler()
    scheduler.register_jobs()
    scheduler.start()
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _APSCHEDULER_AVAILABLE = True
except ImportError:
    _APSCHEDULER_AVAILABLE = False
    logger.warning(
        "APScheduler is not installed. Scheduled jobs will not run. "
        "Add 'apscheduler' to requirements.txt to enable them."
    )


class Scheduler:
    """
    Application job scheduler.

    Wraps AsyncIOScheduler and provides a central location for all
    periodic task registrations.
    """

    def __init__(self) -> None:
        if _APSCHEDULER_AVAILABLE:
            self._scheduler = AsyncIOScheduler()
        else:
            self._scheduler = None
        self.logger = logging.getLogger(__name__)

    def register_jobs(self) -> None:
        """
        Register all background jobs.

        Call once before start(). Add job registrations here as they
        are implemented in later phases.

        TODO (Phase 4): add_job(subscription_expiry_checker, 'interval', hours=1)
        TODO (Phase 4): add_job(server_health_monitor, 'interval', minutes=5)
        TODO (Phase 4): add_job(daily_stats_report, 'cron', hour=8, minute=0)
        """
        self.logger.debug("Scheduler.register_jobs — no jobs registered yet (Phase 4)")

    def add_job(self, func: Callable, trigger: str, **trigger_args) -> None:
        """
        Register a single job with the scheduler.

        Args:
            func:         The async function to call.
            trigger:      APScheduler trigger type: 'interval', 'cron', 'date'.
            **trigger_args: Trigger-specific keyword arguments.
        """
        if self._scheduler is None:
            self.logger.error("Cannot add job — APScheduler not available.")
            return
        self._scheduler.add_job(func, trigger, **trigger_args)
        self.logger.info("Job registered — func=%s trigger=%s", func.__name__, trigger)

    def start(self) -> None:
        """Start the scheduler. Must be called after the event loop is running."""
        if self._scheduler is None:
            return
        self._scheduler.start()
        self.logger.info("Scheduler started")

    def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self.logger.info("Scheduler stopped")
