from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.services.background_job_service import BackgroundJobService
from database.connection import DatabaseManager
from database.models.background_job import BackgroundJobORM, BackgroundJobStatus


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'phase73_jobs.db'}"


async def _db(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    return db


@pytest.mark.asyncio
async def test_logical_key_deduplication_and_owner_safe_completion(tmp_path):
    db = await _db(tmp_path)
    service = BackgroundJobService(db)
    first, second = await asyncio.gather(
        service.enqueue(job_type="reward_retry", logical_key="reward-retry:42"),
        service.enqueue(job_type="reward_retry", logical_key="reward-retry:42"),
    )
    assert sorted([first.created, second.created]) == [False, True]
    lease = await service.acquire(worker_id="worker-a")
    assert lease is not None
    assert await service.complete(job_id=lease.job_id, worker_id="worker-b") is False
    assert await service.complete(job_id=lease.job_id, worker_id="worker-a") is True
    async with db.session() as session:
        rows = list((await session.execute(select(BackgroundJobORM))).scalars().all())
        assert len(rows) == 1
        assert rows[0].status == BackgroundJobStatus.SUCCEEDED.value
    await db.close()


@pytest.mark.asyncio
async def test_retry_backoff_and_dead_letter_are_bounded(tmp_path):
    db = await _db(tmp_path)
    service = BackgroundJobService(db)
    await service.enqueue(job_type="health_check", logical_key="health-check:db:1", max_attempts=2)
    first = await service.acquire(worker_id="worker-a")
    assert first is not None
    assert await service.fail(job_id=first.job_id, worker_id="worker-a", error_code="temporary", retryable=True) == BackgroundJobStatus.RETRY_WAIT.value
    async with db.session() as session:
        row = (await session.execute(select(BackgroundJobORM))).scalar_one()
        row.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.flush()
    second = await service.acquire(worker_id="worker-b")
    assert second is not None
    assert await service.fail(job_id=second.job_id, worker_id="worker-b", error_code="still_failing", retryable=True) == BackgroundJobStatus.DEAD_LETTER.value
    await db.close()


@pytest.mark.asyncio
async def test_stale_lease_recovery_requeues_or_dead_letters(tmp_path):
    db = await _db(tmp_path)
    service = BackgroundJobService(db)
    await service.enqueue(job_type="vpn_expiration", logical_key="vpn-expire:7:1", max_attempts=3)
    lease = await service.acquire(worker_id="crashed-worker")
    assert lease is not None
    result = await service.recover_stale(now=datetime.now(timezone.utc) + timedelta(hours=1))
    assert result == {"recovered": 1, "dead_lettered": 0}
    recovered = await service.acquire(worker_id="replacement-worker")
    assert recovered is not None
    await db.close()
