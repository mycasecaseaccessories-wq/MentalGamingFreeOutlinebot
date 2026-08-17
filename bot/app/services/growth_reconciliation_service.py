"""Phase 6.6 bounded growth reward reconciliation and stale-state recovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.result import Failure, Success
from app.events import EventType, bus
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.referral_reward import ReferralRewardORM
from database.models.user import UserORM


class GrowthReconciliationService:
    """Admin-only health scan; mutations reuse existing authoritative services."""

    def __init__(self, db, reward_service):
        self.db = db
        self.rewards = reward_service

    async def scan(self, *, actor_user_id: int, stale_after_seconds: int = 900, limit: int = 100):
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or not actor.is_active or actor.role != "admin":
                return Failure("permission_denied", "Admin permission required.")
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=max(60, min(86400, int(stale_after_seconds))))
            rewards = list((await session.execute(
                select(ReferralRewardORM)
                .where(ReferralRewardORM.status.in_([ReferralRewardORM.STATUS_GRANTING, ReferralRewardORM.STATUS_FAILED]))
                .where(ReferralRewardORM.updated_at <= cutoff)
                .order_by(ReferralRewardORM.updated_at.asc())
                .limit(max(1, min(500, int(limit))))
            )).scalars().all())
            entitlements = list((await session.execute(
                select(FreeTrialEntitlementORM)
                .where(FreeTrialEntitlementORM.status == "active")
                .where(FreeTrialEntitlementORM.expires_at.is_not(None))
                .where(FreeTrialEntitlementORM.expires_at <= now)
                .order_by(FreeTrialEntitlementORM.expires_at.asc())
                .limit(max(1, min(500, int(limit))))
            )).scalars().all())
        result = {
            "stale_rewards": [self._reward(row) for row in rewards],
            "expired_entitlements": [self._entitlement(row) for row in entitlements],
            "counts": {"stale_rewards": len(rewards), "expired_entitlements": len(entitlements)},
        }
        await bus.emit(EventType.GROWTH_RECONCILIATION_SCANNED, actor_user_id=actor_user_id, counts=result["counts"])
        return Success(result)

    async def expire_entitlements(self, *, actor_user_id: int, limit: int = 100):
        scan = await self.scan(actor_user_id=actor_user_id, stale_after_seconds=86400, limit=limit)
        if not scan.is_success:
            return scan
        ids = [item["id"] for item in scan.unwrap()["expired_entitlements"]]
        if not ids:
            return Success({"expired": 0})
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or not actor.is_active or actor.role != "admin":
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.id.in_(ids)).with_for_update())).scalars().all())
            changed = 0
            now = datetime.now(timezone.utc)
            for row in rows:
                if row.status == "active" and row.expires_at is not None and row.expires_at <= now:
                    row.status = "expired"
                    changed += 1
                    await bus.emit(EventType.GROWTH_ENTITLEMENT_EXPIRED, actor_user_id=actor_user_id, entitlement_id=row.id, user_id=row.user_id)
            await session.flush()
        return Success({"expired": changed})

    async def release_held_reward(self, *, actor_user_id: int, reward_id: int):
        return await self.rewards.release_held_reward(actor_user_id=actor_user_id, reward_id=reward_id)

    @staticmethod
    def _reward(row):
        return {"id": row.id, "public_reward_id": row.public_reward_id, "source_type": row.source_type, "status": row.status, "updated_at": row.updated_at}

    @staticmethod
    def _entitlement(row):
        return {"id": row.id, "user_id": row.user_id, "source": row.source, "expires_at": row.expires_at, "remaining_uses": row.remaining_uses}
