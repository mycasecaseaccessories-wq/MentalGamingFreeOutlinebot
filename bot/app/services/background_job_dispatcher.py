from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from app.events import EventType, bus
from app.services.background_job_service import BackgroundJobService, JobLease

JobHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class BackgroundJobDispatcher:
    """One-shot durable worker loop; safe for multiple process instances."""

    def __init__(self, job_service: BackgroundJobService, *, worker_id: str | None = None, concurrency: int = 1) -> None:
        self.job_service = job_service
        self.worker_id = worker_id or f"{socket.gethostname()}:{id(self)}"
        self.concurrency = max(1, min(int(concurrency), 20))
        self.handlers: dict[str, JobHandler] = {}
        self.logger = logging.getLogger("services.BackgroundJobDispatcher")

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        if job_type in self.handlers:
            raise ValueError(f"Background handler already registered: {job_type}")
        self.handlers[job_type] = handler

    async def run_once(self) -> int:
        leases: list[JobLease] = []
        for _ in range(self.concurrency):
            lease = await self.job_service.acquire(worker_id=self.worker_id)
            if lease is None:
                break
            leases.append(lease)
        if not leases:
            await self.job_service.recover_stale(limit=50)
            return 0
        await asyncio.gather(*(self._execute(lease) for lease in leases))
        return len(leases)

    async def _execute(self, lease: JobLease) -> None:
        handler = self.handlers.get(lease.job_type)
        if handler is None:
            await self.job_service.fail(job_id=lease.job_id, worker_id=self.worker_id, error_code="handler_not_registered", retryable=False)
            await bus.emit(EventType.BACKGROUND_JOB_FAILED, public_job_id=lease.public_id, job_type=lease.job_type, error_code="handler_not_registered")
            return
        try:
            await self.job_service.mark_running(job_id=lease.job_id, worker_id=self.worker_id)
            await handler(lease.payload_safe)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.logger.exception("Background job failed: %s", lease.public_id)
            status = await self.job_service.fail(job_id=lease.job_id, worker_id=self.worker_id, error_code=type(exc).__name__, error_message=str(exc), retryable=True)
            event = EventType.BACKGROUND_JOB_DEAD_LETTERED if status == "dead_letter" else EventType.BACKGROUND_JOB_FAILED
            await bus.emit(event, public_job_id=lease.public_id, job_type=lease.job_type, error_code=type(exc).__name__, status=status)
        else:
            await self.job_service.complete(job_id=lease.job_id, worker_id=self.worker_id)
            await bus.emit(EventType.BACKGROUND_JOB_COMPLETED, public_job_id=lease.public_id, job_type=lease.job_type)
