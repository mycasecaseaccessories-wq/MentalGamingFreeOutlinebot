from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Success
from app.events import EventType, bus
from database.models.free_trial_rate_limit import FreeTrialRateLimitORM
from database.models.free_trial_upgrade import FreeTrialRestrictionORM
from database.models.user import UserORM


class FreeTrialAbuseProtectionService:
    """Low-data trial risk gate using account state, restrictions, and velocity."""

    def __init__(self, db, *, window_seconds: int = 3, max_events: int = 4, settings_service=None):
        self.db = db
        self.settings = settings_service
        self.window_seconds = max(1, int(window_seconds))
        self.max_events = max(1, int(max_events))

    async def evaluate_claim(self, *, user_id: int):
        return await self._evaluate(user_id=user_id, action="claim")

    async def evaluate_upgrade(self, *, user_id: int, vpn_key_id: int):
        result = await self._evaluate(user_id=user_id, action="upgrade")
        return result

    async def _evaluate(self, *, user_id: int, action: str):
        async with self.db.session() as session:
            user = await session.get(UserORM, user_id)
            if user is None or not user.is_active or user.status in {"banned", "suspended", "inactive"}:
                return Failure("account_restricted", "This account cannot use Free Trial services.")
            restriction = (await session.execute(select(FreeTrialRestrictionORM).where(FreeTrialRestrictionORM.user_id == user_id))).scalar_one_or_none()
            if restriction is not None and restriction.blocked:
                return Failure("free_trial_restricted", "Free Trial access is temporarily restricted.")
        configured_window = self.window_seconds
        if self.settings is not None:
            configured_window = await self.settings.get("free_trial_abuse_rate_limit_seconds", configured_window)
        window_seconds = max(1, int(configured_window))
        allowed = await self._consume_velocity(
            user_id=user_id,
            action=action,
            window_seconds=window_seconds,
        )
        if not allowed:
            return Failure("too_many_requests", "Please try again later.")
        await bus.emit(EventType.FREE_TRIAL_RISK_EVALUATED, user_id=user_id, action=action, result="allow")
        return Success({"decision": "allow"})

    async def _consume_velocity(self, *, user_id: int, action: str, window_seconds: int) -> bool:
        """Atomically consume one durable action slot across all workers."""
        now = datetime.now(timezone.utc)
        for attempt in range(2):
            try:
                async with self.db.session() as session:
                    row = (await session.execute(
                        select(FreeTrialRateLimitORM)
                        .where(
                            FreeTrialRateLimitORM.user_id == user_id,
                            FreeTrialRateLimitORM.action == action,
                        )
                        .with_for_update()
                    )).scalar_one_or_none()
                    if row is None:
                        session.add(FreeTrialRateLimitORM(
                            user_id=user_id,
                            action=action,
                            window_started_at=now,
                            event_count=1,
                        ))
                        return True
                    window_started_at = row.window_started_at
                    if window_started_at.tzinfo is None:
                        window_started_at = window_started_at.replace(tzinfo=timezone.utc)
                    elapsed = (now - window_started_at).total_seconds()
                    if elapsed >= window_seconds:
                        row.window_started_at = now
                        row.event_count = 1
                        return True
                    if row.event_count >= self.max_events:
                        return False
                    row.event_count += 1
                    return True
            except IntegrityError:
                if attempt == 1:
                    raise
                # Two workers may race to create the unique first row. The
                # second attempt observes the committed row under a lock.
                continue
        return False

    async def block_user(self, *, actor_user_id: int, user_id: int, reason: str):
        return await self._set_restriction(actor_user_id=actor_user_id, user_id=user_id, blocked=True, reason=reason)

    async def unblock_user(self, *, actor_user_id: int, user_id: int):
        return await self._set_restriction(actor_user_id=actor_user_id, user_id=user_id, blocked=False, reason=None)

    async def _set_restriction(self, *, actor_user_id: int, user_id: int, blocked: bool, reason: str | None):
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or actor.role != "admin" or not actor.is_active:
                return Failure("permission_denied", "Admin permission required.")
            row = (await session.execute(select(FreeTrialRestrictionORM).where(FreeTrialRestrictionORM.user_id == user_id).with_for_update())).scalar_one_or_none()
            if row is None:
                row = FreeTrialRestrictionORM(user_id=user_id)
                session.add(row)
            row.blocked = blocked; row.reason = (reason or "")[:255] or None; row.updated_by = actor_user_id; row.blocked_at = datetime.now(timezone.utc) if blocked else None
        await bus.emit(EventType.FREE_TRIAL_RISK_EVALUATED, user_id=user_id, action="restriction", result="blocked" if blocked else "unblocked")
        return Success({"user_id": user_id, "blocked": blocked})
