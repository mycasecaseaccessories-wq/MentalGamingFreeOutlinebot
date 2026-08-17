"""Phase 6.6 unified growth reward and entitlement read facade.

The authoritative grant path remains ReferralRewardService.  This facade only
normalizes provenance/history/entitlement presentation and delegates mutations
to existing idempotent services.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Success
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.free_trial_entitlement_redemption import FreeTrialEntitlementRedemptionORM
from database.models.referral_reward import ReferralRewardORM
from database.models.user import UserORM


class GrowthRewardService:
    """Unified read model for Referral, Mission, Promo, and Admin rewards."""

    SOURCE_LABELS = {
        "referral": "referral",
        "mission": "mission",
        "promo": "promo",
        "admin": "admin",
        "system": "system",
    }
    REWARD_TYPE_ALIASES = {
        "extra_free_trial": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "extra_trial": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "mission_trial_bonus": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "promo_free_claim": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "wallet_credit": ReferralRewardORM.TYPE_WALLET_CREDIT,
        "bonus_data": ReferralRewardORM.TYPE_BONUS_DATA,
        "bonus_duration": ReferralRewardORM.TYPE_BONUS_DURATION,
        "promo_entitlement": "promo_entitlement",
        "discount": "discount",
        "none": "none",
    }

    def __init__(self, db, reward_service=None, mission_progress_service=None):
        self.db = db
        self.rewards = reward_service
        self.missions = mission_progress_service

    async def customer_center(self, user_id: int, *, limit: int = 20):
        async with self.db.session() as session:
            rows = list((await session.execute(
                select(ReferralRewardORM)
                .where(ReferralRewardORM.beneficiary_user_id == user_id)
                .order_by(ReferralRewardORM.created_at.desc())
                .limit(max(1, min(50, int(limit))))
            )).scalars().all())
            entitlements = list((await session.execute(
                select(FreeTrialEntitlementORM)
                .where(FreeTrialEntitlementORM.user_id == user_id)
                .order_by(FreeTrialEntitlementORM.created_at.desc())
                .limit(max(1, min(50, int(limit))))
            )).scalars().all())
        return Success({
            "rewards": [self._reward(row) for row in rows],
            "entitlements": [self._entitlement(row) for row in entitlements],
            "counts": {
                "rewards": len(rows),
                "granted": sum(row.status == ReferralRewardORM.STATUS_GRANTED for row in rows),
                "pending": sum(row.status in {ReferralRewardORM.STATUS_PENDING, ReferralRewardORM.STATUS_GRANTING, ReferralRewardORM.STATUS_REVIEW_REQUIRED} for row in rows),
                "available_entitlements": sum(self._entitlement_available(row) for row in entitlements),
            },
        })

    async def list_entitlements(self, user_id: int, *, status: str | None = None, limit: int = 50):
        async with self.db.session() as session:
            query = select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.user_id == user_id)
            if status:
                query = query.where(FreeTrialEntitlementORM.status == status)
            rows = list((await session.execute(query.order_by(FreeTrialEntitlementORM.created_at.desc()).limit(max(1, min(100, int(limit)))))).scalars().all())
        return Success([self._entitlement(row) for row in rows])

    async def reward_history(self, user_id: int, *, source_type: str | None = None, status: str | None = None, limit: int = 50):
        async with self.db.session() as session:
            query = select(ReferralRewardORM).where(ReferralRewardORM.beneficiary_user_id == user_id)
            if source_type:
                query = query.where(ReferralRewardORM.source_type == source_type)
            if status:
                query = query.where(ReferralRewardORM.status == status)
            rows = list((await session.execute(query.order_by(ReferralRewardORM.created_at.desc()).limit(max(1, min(100, int(limit)))))).scalars().all())
        return Success([self._reward(row) for row in rows])

    async def admin_overview(self, actor_user_id: int):
        async with self.db.session() as session:
            if not await self._is_admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralRewardORM))).scalars().all())
            entitlements = list((await session.execute(select(FreeTrialEntitlementORM))).scalars().all())
        by_source: dict[str, dict[str, int]] = {}
        for row in rows:
            source = by_source.setdefault(row.source_type, {"total": 0, "granted": 0, "pending": 0, "failed": 0, "held": 0})
            source["total"] += 1
            source["granted"] += row.status == ReferralRewardORM.STATUS_GRANTED
            source["pending"] += row.status in {ReferralRewardORM.STATUS_PENDING, ReferralRewardORM.STATUS_GRANTING}
            source["failed"] += row.status == ReferralRewardORM.STATUS_FAILED
            source["held"] += row.status == ReferralRewardORM.STATUS_REVIEW_REQUIRED
        return Success({
            "total_rewards": len(rows),
            "granted": sum(row.status == ReferralRewardORM.STATUS_GRANTED for row in rows),
            "pending": sum(row.status in {ReferralRewardORM.STATUS_PENDING, ReferralRewardORM.STATUS_GRANTING} for row in rows),
            "failed": sum(row.status == ReferralRewardORM.STATUS_FAILED for row in rows),
            "held": sum(row.status == ReferralRewardORM.STATUS_REVIEW_REQUIRED for row in rows),
            "entitlements": len(entitlements),
            "available_entitlements": sum(self._entitlement_available(row) for row in entitlements),
            "by_source": by_source,
        })

    async def admin_reward_search(self, actor_user_id: int, *, public_reward_id: str | None = None, source_type: str | None = None, status: str | None = None, limit: int = 50):
        async with self.db.session() as session:
            if not await self._is_admin(session, actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            query = select(ReferralRewardORM)
            if public_reward_id:
                query = query.where(ReferralRewardORM.public_reward_id == public_reward_id)
            if source_type:
                query = query.where(ReferralRewardORM.source_type == source_type)
            if status:
                query = query.where(ReferralRewardORM.status == status)
            rows = list((await session.execute(query.order_by(ReferralRewardORM.created_at.desc()).limit(max(1, min(100, int(limit)))))).scalars().all())
        return Success([self._reward(row, include_admin=True) for row in rows])

    async def consume_entitlement(self, *, user_id: int, entitlement_id: int, idempotency_key: str, units: int = 1):
        """Consume an entitlement once, with database-backed idempotency."""
        units = int(units)
        if units <= 0 or units > 100:
            return Failure("invalid_units", "Invalid entitlement quantity.")
        async with self.db.session() as session:
            existing = (await session.execute(select(FreeTrialEntitlementRedemptionORM).where(FreeTrialEntitlementRedemptionORM.idempotency_key == idempotency_key))).scalar_one_or_none()
            if existing is not None:
                return Success({"status": "already_redeemed", "redemption_id": existing.id, "entitlement_id": existing.entitlement_id})
            entitlement = (await session.execute(select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.id == entitlement_id, FreeTrialEntitlementORM.user_id == user_id).with_for_update())).scalar_one_or_none()
            if entitlement is None:
                return Failure("not_found", "Entitlement not found.")
            now = datetime.now(timezone.utc)
            expires = entitlement.expires_at
            if expires is not None and (expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)) <= now:
                entitlement.status = "expired"
                await session.flush()
                return Failure("expired", "Entitlement expired.")
            if entitlement.status != "active" or int(entitlement.remaining_uses or 0) < units:
                return Failure("not_available", "Entitlement is not available.")
            redemption = FreeTrialEntitlementRedemptionORM(entitlement_id=entitlement.id, user_id=user_id, idempotency_key=str(idempotency_key)[:160], units=units, consumed_at=now, status="redeemed")
            session.add(redemption)
            entitlement.remaining_uses -= units
            if entitlement.remaining_uses <= 0:
                entitlement.remaining_uses = 0
                entitlement.status = "redeemed"
            await session.flush()
            return Success({"status": "redeemed", "redemption_id": redemption.id, "entitlement_id": entitlement.id, "remaining_uses": entitlement.remaining_uses})

    async def claim_mission_reward(self, *, user_id: int, public_progress_id: str):
        if self.missions is None:
            return Failure("unavailable", "Mission reward service unavailable.")
        return Success(await self.missions.claim_reward(user_id=user_id, public_progress_id=public_progress_id))

    async def release_held_reward(self, *, actor_user_id: int, reward_id: int):
        if self.rewards is None:
            return Failure("unavailable", "Reward service unavailable.")
        return await self.rewards.release_held_reward(actor_user_id=actor_user_id, reward_id=reward_id)

    @classmethod
    def normalize_reward_type(cls, value: str | None) -> str:
        return cls.REWARD_TYPE_ALIASES.get(str(value or "none").lower(), str(value or "none").lower())

    @classmethod
    def format_reward(cls, reward_type: str, value) -> str:
        reward_type = cls.normalize_reward_type(reward_type)
        amount = Decimal(str(value or 0))
        if reward_type == ReferralRewardORM.TYPE_EXTRA_TRIAL:
            count = int(amount) if amount == amount.to_integral_value() else amount
            return f"{count} extra trial" if amount == 1 else f"{count} extra trials"
        if reward_type == ReferralRewardORM.TYPE_WALLET_CREDIT:
            return f"{amount:,.2f} wallet credit" if amount != amount.to_integral_value() else f"{int(amount):,} wallet credit"
        if reward_type == ReferralRewardORM.TYPE_BONUS_DATA:
            return f"{cls._bytes(amount)} bonus data"
        if reward_type == ReferralRewardORM.TYPE_BONUS_DURATION:
            return f"{cls._duration(int(amount))} bonus duration"
        return str(value or "—")

    @classmethod
    def _reward(cls, row, *, include_admin: bool = False):
        result = {
            "public_reward_id": row.public_reward_id,
            "source_type": cls.SOURCE_LABELS.get(row.source_type, "other"),
            "source_reference": str(row.source_reference or "")[:80],
            "reward_type": cls.normalize_reward_type(row.reward_type),
            "reward_value": str(row.reward_value),
            "reward_label": cls.format_reward(row.reward_type, row.reward_value),
            "status": row.status,
            "created_at": row.created_at,
            "granted_at": row.granted_at,
            "expires_at": (row.policy_snapshot_json or {}).get("expiry_at"),
        }
        if include_admin:
            result.update({"user_id": row.beneficiary_user_id, "risk_result": row.risk_result, "limit_result": row.limit_result, "failure_reason": row.failure_reason})
        return result

    @staticmethod
    def _entitlement_available(row) -> bool:
        expires = row.expires_at
        not_expired = expires is None or (expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc)
        return row.status == "active" and int(row.remaining_uses or 0) > 0 and not_expired

    @classmethod
    def _entitlement(cls, row):
        return {
            "id": row.id,
            "source": str(row.source),
            "remaining_uses": int(row.remaining_uses or 0),
            "data_limit_bytes": row.data_limit_bytes,
            "data_label": cls._bytes(row.data_limit_bytes) if row.data_limit_bytes else None,
            "duration_seconds": row.duration_seconds,
            "duration_label": cls._duration(row.duration_seconds) if row.duration_seconds else None,
            "device_limit": row.device_limit,
            "expires_at": row.expires_at,
            "status": "available" if cls._entitlement_available(row) else ("expired" if row.expires_at and row.expires_at <= datetime.now(timezone.utc) else row.status),
        }

    async def _is_admin(self, session, actor_user_id: int) -> bool:
        actor = await session.get(UserORM, actor_user_id)
        return actor is not None and actor.is_active and actor.role == "admin"

    @staticmethod
    def _bytes(value) -> str:
        amount = float(value or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1024 or unit == "TB":
                return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.2f} {unit}".rstrip("0").rstrip(".")
            amount /= 1024
        return f"{amount:.2f} TB"

    @staticmethod
    def _duration(seconds: int) -> str:
        seconds = int(seconds or 0)
        if seconds % 86400 == 0:
            return f"{seconds // 86400} day(s)"
        if seconds % 3600 == 0:
            return f"{seconds // 3600} hour(s)"
        return f"{seconds // 60} minute(s)"
