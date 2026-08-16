"""
NotificationRepository — data access for the notifications table.

Tracks outbound notifications for auditing, retry logic, and
deduplication. NotificationService writes records here.
"""

from __future__ import annotations

from typing import List

from sqlalchemy import select

from database.models.notification import NotificationORM
from .base import BaseRepository


class NotificationRepository(BaseRepository[NotificationORM, NotificationORM]):
    """
    Handles all database operations for the notifications table.

    Phase 0.2: CRUD inherited; delivery queue helpers stubbed.
    Phase 1:   NotificationService writes a record before sending and
               updates status + sent_at / error after the attempt.
    """

    orm_class    = NotificationORM
    domain_class = NotificationORM

    async def get_queued(self, limit: int = 50) -> List[NotificationORM]:
        """
        Return up to limit queued notifications pending dispatch.

        Used by the scheduler to process the outbox in batches.
        """
        stmt = (
            select(NotificationORM)
            .where(NotificationORM.status == NotificationORM.STATUS_QUEUED)
            .order_by(NotificationORM.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(self, notification_id: int) -> None:
        """Update a notification to status=sent and record sent_at."""
        from datetime import datetime, timezone
        await self.update(
            notification_id,
            status=NotificationORM.STATUS_SENT,
            sent_at=datetime.now(timezone.utc),
        )

    async def mark_failed(self, notification_id: int, error: str) -> None:
        """Update a notification to status=failed and store the error detail."""
        await self.update(
            notification_id,
            status=NotificationORM.STATUS_FAILED,
            error=error[:2000],  # Truncate to column length.
        )

    async def get_history_for_user(
        self, user_id: int, limit: int = 20
    ) -> List[NotificationORM]:
        """Return the most recently sent notifications for a user."""
        stmt = (
            select(NotificationORM)
            .where(
                NotificationORM.user_id == user_id,
                NotificationORM.status == NotificationORM.STATUS_SENT,
            )
            .order_by(NotificationORM.sent_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
