"""Mock scheduler — prevents real APScheduler from starting during tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class MockScheduler:
    """Mock for app.scheduler.base.Scheduler."""

    def __init__(self) -> None:
        self._running = False
        self._jobs: list[dict[str, Any]] = []

        self.start = MagicMock(side_effect=self._do_start)
        self.shutdown = MagicMock(side_effect=self._do_shutdown)
        self.add_job = MagicMock(side_effect=self._record_job)
        self.remove_job = MagicMock(return_value=True)
        self.get_jobs = MagicMock(return_value=[])
        self.is_running = MagicMock(side_effect=lambda: self._running)

    def _do_start(self) -> None:
        self._running = True

    def _do_shutdown(self, wait: bool = True) -> None:
        self._running = False

    def _record_job(self, func: Any, **kwargs: Any) -> MagicMock:
        job = MagicMock()
        job.id = kwargs.get("id", f"job_{len(self._jobs)}")
        self._jobs.append({"func": func, "kwargs": kwargs, "job": job})
        return job

    @property
    def job_count(self) -> int:
        return len(self._jobs)
