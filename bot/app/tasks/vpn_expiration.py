from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select

from app.models.enums import VPNKeyStatus
from app.models.vpn_lifecycle import ProviderCleanupStatus
from app.tasks.base import BaseTask, TaskContext
from database.models.vpn_key import VPNKeyORM


@dataclass(frozen=True, slots=True)
class ExpirationSweepResult:
    scanned: int
    expired: int
    completed: int
    failed: int
    skipped: int


class VPNExpirationSweepTask(BaseTask):
    name = "vpn-expiration-sweep"

    def __init__(self, *, db, lifecycle_service, batch_size: int = 100) -> None:
        self.db = db
        self.lifecycle_service = lifecycle_service
        self.batch_size = max(1, min(int(batch_size), 1000))

    async def run(self, context: TaskContext | None = None) -> ExpirationSweepResult:
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            rows = list((await session.execute(
                select(VPNKeyORM.id)
                .where(
                    VPNKeyORM.status.in_((VPNKeyStatus.ACTIVE.value, VPNKeyStatus.SUSPENDED.value)),
                    VPNKeyORM.expires_at.is_not(None),
                    VPNKeyORM.expires_at <= now,
                    VPNKeyORM.lifecycle_cleanup_status.in_((ProviderCleanupStatus.NOT_REQUIRED.value, ProviderCleanupStatus.FAILED.value, ProviderCleanupStatus.PENDING.value)),
                )
                .order_by(VPNKeyORM.expires_at.asc())
                .limit(self.batch_size)
            )).scalars().all())
        completed = failed = skipped = 0
        for key_id in rows:
            result = await self.lifecycle_service.expire_due_key(key_id=int(key_id))
            if result.is_success:
                completed += 1
            elif result.error and result.error.code == "not_due":
                skipped += 1
            else:
                failed += 1
        return ExpirationSweepResult(len(rows), len(rows) - skipped, completed, failed, skipped)
