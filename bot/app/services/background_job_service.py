from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService
from app.events import EventType, bus
from database.models.background_job import BackgroundJobORM, BackgroundJobStatus


@dataclass(frozen=True, slots=True)
class JobLease:
    job_id: int
    public_id: str
    job_type: str
    logical_key: str
    payload_safe: dict
    attempt_count: int
    timeout_seconds: int
    lease_owner: str
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class JobEnqueueResult:
    job_id: int
    public_id: str
    logical_key: str
    created: bool
    status: str


class BackgroundJobService(BaseService):
    """Durable job state machine; domain handlers remain outside this service."""

    def __init__(self, db=None, *, default_max_attempts: int = 5, default_lease_seconds: int = 300) -> None:
        super().__init__(db)
        self.default_max_attempts = max(1, min(int(default_max_attempts), 50))
        self.default_lease_seconds = max(30, min(int(default_lease_seconds), 3600))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def enqueue(
        self,
        *,
        job_type: str,
        logical_key: str,
        payload_safe: dict | None = None,
        scheduled_for: datetime | None = None,
        priority: int = 100,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        correlation_id: str | None = None,
    ) -> JobEnqueueResult:
        now = self._now()
        available = scheduled_for or now
        async with self.db.session() as session:
            existing = (await session.execute(select(BackgroundJobORM).where(BackgroundJobORM.logical_key == logical_key))).scalar_one_or_none()
            if existing is not None:
                return JobEnqueueResult(existing.id, existing.public_id, existing.logical_key, False, existing.status)
            row = BackgroundJobORM(
                public_id=f"job_{uuid.uuid4().hex[:24]}",
                job_type=job_type,
                logical_key=logical_key,
                status=BackgroundJobStatus.READY.value if available <= now else BackgroundJobStatus.PENDING.value,
                priority=max(0, min(int(priority), 1000)),
                payload_safe=dict(payload_safe or {}),
                scheduled_for=scheduled_for,
                available_at=available,
                max_attempts=max(1, min(int(max_attempts or self.default_max_attempts), 50)),
                timeout_seconds=max(30, min(int(timeout_seconds or self.default_lease_seconds), 3600)),
                correlation_id=correlation_id,
            )
            session.add(row)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                existing = (await session.execute(select(BackgroundJobORM).where(BackgroundJobORM.logical_key == logical_key))).scalar_one()
                return JobEnqueueResult(existing.id, existing.public_id, existing.logical_key, False, existing.status)
            result = JobEnqueueResult(row.id, row.public_id, row.logical_key, True, row.status)
            await bus.emit(EventType.BACKGROUND_JOB_ENQUEUED, public_job_id=row.public_id, job_type=row.job_type, logical_key=row.logical_key)
            return result

    async def acquire(self, *, worker_id: str, now: datetime | None = None) -> JobLease | None:
        now = now or self._now()
        async with self.db.session() as session:
            query = (
                select(BackgroundJobORM)
                .where(
                    BackgroundJobORM.status.in_((BackgroundJobStatus.READY.value, BackgroundJobStatus.RETRY_WAIT.value, BackgroundJobStatus.PENDING.value)),
                    BackgroundJobORM.available_at <= now,
                    or_(BackgroundJobORM.scheduled_for.is_(None), BackgroundJobORM.scheduled_for <= now),
                )
                .order_by(BackgroundJobORM.priority.desc(), BackgroundJobORM.available_at.asc(), BackgroundJobORM.id.asc())
                .limit(1)
                .with_for_update()
            )
            row = (await session.execute(query)).scalar_one_or_none()
            if row is None:
                return None
            row.status = BackgroundJobStatus.LEASED.value
            row.lease_owner = worker_id
            row.lease_acquired_at = now
            row.last_heartbeat_at = now
            row.lease_expires_at = now + timedelta(seconds=row.timeout_seconds)
            row.started_at = row.started_at or now
            row.attempt_count = int(row.attempt_count or 0) + 1
            await session.flush()
            return JobLease(row.id, row.public_id, row.job_type, row.logical_key, dict(row.payload_safe or {}), row.attempt_count, row.timeout_seconds, worker_id, row.lease_expires_at)

    async def mark_running(self, *, job_id: int, worker_id: str) -> bool:
        async with self.db.session() as session:
            row = await self._owned_row(session, job_id, worker_id)
            if row is None or row.status != BackgroundJobStatus.LEASED.value:
                return False
            row.status = BackgroundJobStatus.RUNNING.value
            await session.flush()
            return True

    async def heartbeat(self, *, job_id: int, worker_id: str, lease_seconds: int | None = None) -> bool:
        now = self._now()
        async with self.db.session() as session:
            row = await self._owned_row(session, job_id, worker_id)
            if row is None or row.status not in (BackgroundJobStatus.LEASED.value, BackgroundJobStatus.RUNNING.value):
                return False
            seconds = max(30, min(int(lease_seconds or row.timeout_seconds), 3600))
            row.last_heartbeat_at = now
            row.lease_expires_at = now + timedelta(seconds=seconds)
            await session.flush()
            return True

    async def complete(self, *, job_id: int, worker_id: str, status: str = BackgroundJobStatus.SUCCEEDED.value) -> bool:
        now = self._now()
        async with self.db.session() as session:
            row = await self._owned_row(session, job_id, worker_id)
            if row is None or row.status not in (BackgroundJobStatus.LEASED.value, BackgroundJobStatus.RUNNING.value):
                return row is not None and row.status == BackgroundJobStatus.SUCCEEDED.value
            row.status = status
            row.finished_at = now
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_heartbeat_at = now
            await session.flush()
            return True

    async def fail(self, *, job_id: int, worker_id: str, error_code: str, error_message: str | None = None, retryable: bool = True) -> str | None:
        now = self._now()
        async with self.db.session() as session:
            row = await self._owned_row(session, job_id, worker_id)
            if row is None or row.status not in (BackgroundJobStatus.LEASED.value, BackgroundJobStatus.RUNNING.value):
                return None
            row.last_error_code = str(error_code)[:128]
            row.last_error_message = (error_message or "")[:1000] or None
            row.lease_owner = None
            row.lease_expires_at = None
            if not retryable or row.attempt_count >= row.max_attempts:
                row.status = BackgroundJobStatus.DEAD_LETTER.value if retryable else BackgroundJobStatus.FAILED.value
                row.finished_at = now
            else:
                delay = min(3600, 2 ** max(0, row.attempt_count - 1) * 5)
                row.status = BackgroundJobStatus.RETRY_WAIT.value
                row.available_at = now + timedelta(seconds=delay)
            await session.flush()
            return row.status

    async def recover_stale(self, *, now: datetime | None = None, limit: int = 100) -> dict[str, int]:
        now = now or self._now()
        recovered = dead_lettered = 0
        async with self.db.session() as session:
            rows = list((await session.execute(select(BackgroundJobORM).where(BackgroundJobORM.status.in_((BackgroundJobStatus.LEASED.value, BackgroundJobStatus.RUNNING.value)), BackgroundJobORM.lease_expires_at.is_not(None), BackgroundJobORM.lease_expires_at < now).order_by(BackgroundJobORM.lease_expires_at.asc()).limit(max(1, min(int(limit), 500))).with_for_update())).scalars().all())
            for row in rows:
                row.lease_owner = None
                row.lease_expires_at = None
                row.last_error_code = "stale_lease_recovered"
                if row.attempt_count >= row.max_attempts:
                    row.status = BackgroundJobStatus.DEAD_LETTER.value
                    row.finished_at = now
                    dead_lettered += 1
                else:
                    row.status = BackgroundJobStatus.RETRY_WAIT.value
                    row.available_at = self._now()
                    recovered += 1
            await session.flush()
        if recovered or dead_lettered:
            await bus.emit(EventType.BACKGROUND_JOB_RECOVERED, recovered=recovered, dead_lettered=dead_lettered)
        return {"recovered": recovered, "dead_lettered": dead_lettered}

    async def list_jobs(self, *, statuses: tuple[str, ...] | None = None, limit: int = 100) -> list[dict]:
        async with self.db.session() as session:
            query = select(BackgroundJobORM).order_by(BackgroundJobORM.updated_at.desc()).limit(max(1, min(int(limit), 500)))
            if statuses:
                query = query.where(BackgroundJobORM.status.in_(statuses))
            rows = list((await session.execute(query)).scalars().all())
            return [self._safe(row) for row in rows]

    async def _owned_row(self, session, job_id: int, worker_id: str):
        return (await session.execute(select(BackgroundJobORM).where(BackgroundJobORM.id == job_id, BackgroundJobORM.lease_owner == worker_id).with_for_update())).scalar_one_or_none()

    @staticmethod
    def _safe(row: BackgroundJobORM) -> dict:
        return {"public_id": row.public_id, "job_type": row.job_type, "logical_key": row.logical_key, "status": row.status, "priority": row.priority, "attempt_count": row.attempt_count, "max_attempts": row.max_attempts, "lease_owner": row.lease_owner, "scheduled_for": row.scheduled_for, "available_at": row.available_at, "started_at": row.started_at, "finished_at": row.finished_at, "last_error_code": row.last_error_code, "correlation_id": row.correlation_id}
