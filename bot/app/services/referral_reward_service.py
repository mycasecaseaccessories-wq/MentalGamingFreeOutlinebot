from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import secrets

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Success
from app.events import EventType, bus
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.referral import ReferralORM
from database.models.referral_reward import ReferralRewardORM
from database.models.transaction import TransactionORM
from database.models.wallet import WalletORM
from database.models.user import UserORM
from app.services.maintenance_service import MaintenanceService, MaintenanceBlockedError


class ReferralRewardService:
    _idempotency_locks: dict[str, asyncio.Lock] = {}

    """Authoritative reward ledger and fulfillment service.

    Every beneficiary has an independent reward row.  Database uniqueness is
    deliberately relied on in addition to application checks, so retries and
    concurrent workers cannot create a second logical grant.
    """

    def __init__(self, db, settings_service, maintenance_service: MaintenanceService | None = None):
        self.db = db
        self.settings = settings_service
        self.maintenance_service = maintenance_service

    async def build_rewards(self, referral_id: int):
        async with self.db.session() as session:
            referral = (await session.execute(select(ReferralORM).where(ReferralORM.id == referral_id))).scalar_one_or_none()
            if referral is None or referral.status != ReferralORM.STATUS_QUALIFIED:
                return Success({"created": 0, "reason": "not_qualified"})
            if not bool(await self.settings.get("referral_rewards_enabled", True)):
                return Success({"created": 0, "reason": "disabled"})
            required = max(1, int(await self.settings.get("referral_required_qualified_count", 3)))
            mode = str(await self.settings.get("referral_reward_mode", "every_n"))
            qualified_count = await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.referrer_id == referral.referrer_id, ReferralORM.status.in_([ReferralORM.STATUS_QUALIFIED, ReferralORM.STATUS_REWARDED])))
            qualified_count = int(qualified_count or 0)
            if mode == "every_n":
                cycle = qualified_count // required if qualified_count >= required else 0
            else:
                cycle = qualified_count
            if cycle <= 0:
                return Success({"created": 0, "reason": "threshold_pending", "qualified_count": qualified_count})
            policy = await self._policy_snapshot()
            specs = (
                (ReferralRewardORM.BENEFICIARY_REFERRER, referral.referrer_id, policy["referrer_type"], policy["referrer_value"]),
                (ReferralRewardORM.BENEFICIARY_REFERRED_USER, referral.referred_id, policy["referred_type"], policy["referred_value"]),
            )
        results = []
        for beneficiary, user_id, reward_type, value in specs:
            results.append(await self._create_and_grant(referral_id, beneficiary, user_id, reward_type, value, cycle, policy, source_type="referral", source_reference=str(referral_id)))
        return Success({"created": len(results), "rewards": results, "qualified_count": qualified_count, "cycle": cycle})

    async def grant_reward(self, *, user_id: int, reward_type: str, reward_value: Decimal, source_reference: str, period_key: str, policy_revision: int = 1, reward_expiry_seconds: int = 0, delivery_mode: str = "auto_grant", apply_limits: bool = False, source_type: str = "mission"):
        """Grant a non-referral reward through the same Phase 6.2 ledger/fulfillment path."""
        if self.maintenance_service is not None:
            try:
                await self.maintenance_service.assert_operation_allowed("rewards", "GRANT")
            except MaintenanceBlockedError:
                return {"status": ReferralRewardORM.STATUS_FAILED, "error": "maintenance_active"}
        reward_type = _normalize_reward_type(reward_type)
        if delivery_mode not in {"auto_grant", "manual_claim"}:
            raise ValueError("unsupported_delivery_mode")
        if reward_type == ReferralRewardORM.TYPE_EXTRA_TRIAL:
            beneficiary = "mission"
        elif reward_type in {ReferralRewardORM.TYPE_WALLET_CREDIT, ReferralRewardORM.TYPE_BONUS_DATA, ReferralRewardORM.TYPE_BONUS_DURATION}:
            beneficiary = "mission"
        elif reward_type == "none":
            return {"status": ReferralRewardORM.STATUS_GRANTED, "reward_type": reward_type, "reward_value": "0", "source_type": "mission"}
        else:
            raise ValueError("unsupported_reward_type")
        policy = {
            "revision": int(policy_revision),
            "required_count": 0,
            "mode": "mission",
            "daily_limit": max(0, int(await self.settings.get("mission_reward_daily_limit", 0))),
            "weekly_limit": max(0, int(await self.settings.get("mission_reward_weekly_limit", 0))),
            "monthly_limit": max(0, int(await self.settings.get("mission_reward_monthly_limit", 0))),
            "lifetime_limit": max(0, int(await self.settings.get("mission_reward_lifetime_limit", 0))),
            "global_daily_limit": max(0, int(await self.settings.get("growth_reward_global_daily_limit", 0))),
            "global_weekly_limit": max(0, int(await self.settings.get("growth_reward_global_weekly_limit", 0))),
            "global_lifetime_limit": max(0, int(await self.settings.get("growth_reward_global_lifetime_limit", 0))),
            "cooldown_seconds": max(0, int(await self.settings.get("mission_reward_cooldown_seconds", 0))),
            "expiry_seconds": max(0, int(reward_expiry_seconds)),
            "wallet_currency": str(await self.settings.get("currency", "MMK")).upper()[:3],
        }
        return await self._create_and_grant(None, beneficiary, user_id, reward_type, Decimal(str(reward_value)), 1, policy, source_type=source_type, source_reference=source_reference, apply_limits=apply_limits, explicit_key=f"{source_type}:{source_reference}:{user_id}:{period_key}")

    async def _policy_snapshot(self):
        return {
            "revision": int(await self.settings.get("referral_policy_revision", 1)),
            "required_count": max(1, int(await self.settings.get("referral_required_qualified_count", 3))),
            "mode": str(await self.settings.get("referral_reward_mode", "every_n")),
            "referrer_type": str(await self.settings.get("referral_referrer_reward_type", "extra_trial")),
            "referrer_value": Decimal(str(await self.settings.get("referral_referrer_reward_value", 1))),
            "referred_type": str(await self.settings.get("referral_referred_reward_type", "extra_trial")),
            "referred_value": Decimal(str(await self.settings.get("referral_referred_reward_value", 1))),
            "daily_limit": max(0, int(await self.settings.get("referral_reward_daily_limit", 5))),
            "weekly_limit": max(0, int(await self.settings.get("referral_reward_weekly_limit", 20))),
            "monthly_limit": max(0, int(await self.settings.get("referral_reward_monthly_limit", 50))),
            "lifetime_limit": max(0, int(await self.settings.get("referral_reward_lifetime_limit", 0))),
            "global_daily_limit": max(0, int(await self.settings.get("growth_reward_global_daily_limit", 0))),
            "global_weekly_limit": max(0, int(await self.settings.get("growth_reward_global_weekly_limit", 0))),
            "global_lifetime_limit": max(0, int(await self.settings.get("growth_reward_global_lifetime_limit", 0))),
            "cooldown_seconds": max(0, int(await self.settings.get("referral_reward_cooldown_seconds", 3600))),
            "expiry_seconds": max(0, int(await self.settings.get("referral_reward_expiry_seconds", 2592000))),
            "wallet_currency": str(await self.settings.get("referral_reward_wallet_currency", "MMK")).upper()[:3],
        }

    async def _create_and_grant(self, referral_id, beneficiary, user_id, reward_type, value, cycle, policy, *, source_type="referral", source_reference=None, apply_limits=True, explicit_key=None):
        key = explicit_key or (f"referral_reward:{policy['revision']}:{referral_id}:{beneficiary}:{cycle}" if source_type == "referral" else f"{source_type}_reward:{source_reference}:{beneficiary}:{cycle}")
        lock = self._idempotency_locks.setdefault(key, asyncio.Lock())
        async with lock:
            return await self._create_and_grant_locked(referral_id, beneficiary, user_id, reward_type, value, cycle, policy, key, source_type, source_reference or str(referral_id), apply_limits)

    async def _create_and_grant_locked(self, referral_id, beneficiary, user_id, reward_type, value, cycle, policy, key, source_type, source_reference, apply_limits):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            existing = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.idempotency_key == key).with_for_update())).scalar_one_or_none()
            if existing is not None and existing.status != ReferralRewardORM.STATUS_FAILED:
                return self._result(existing)
            blocked = False
            if source_type == "referral":
                beneficiary_user = await session.get(UserORM, user_id)
                blocked = bool(beneficiary_user and beneficiary_user.referral_reward_blocked)
            allowed, reason = await self._within_limits(session, user_id, policy, now) if apply_limits else (True, "not_shared")
            if blocked:
                allowed, reason = False, "referral_reward_blocked"
            row = existing or ReferralRewardORM(
                public_reward_id="RWD-" + secrets.token_urlsafe(7).replace("_", "-").replace("/", "-")[:10].upper(),
                referral_id=referral_id,
                source_type=source_type,
                source_reference=str(source_reference),
                beneficiary_user_id=user_id,
                beneficiary_type=beneficiary,
                reward_type=reward_type,
                reward_value=value,
                reward_cycle=cycle,
                policy_revision=policy["revision"],
                policy_snapshot_json={k: (str(v) if isinstance(v, Decimal) else v) for k, v in policy.items()},
                status=ReferralRewardORM.STATUS_PENDING if allowed else ReferralRewardORM.STATUS_REVIEW_REQUIRED if reason == "referral_reward_blocked" else ReferralRewardORM.STATUS_LIMIT_REACHED,
                idempotency_key=key,
                limit_result="eligible" if allowed else reason,
                risk_result="blocked" if reason == "referral_reward_blocked" else "safe",
            ) if existing is None else row
            if existing is not None:
                row.status = ReferralRewardORM.STATUS_PENDING if allowed else ReferralRewardORM.STATUS_REVIEW_REQUIRED if reason == "referral_reward_blocked" else ReferralRewardORM.STATUS_LIMIT_REACHED
                row.limit_result = "eligible" if allowed else reason
                row.risk_result = "blocked" if reason == "referral_reward_blocked" else row.risk_result
                row.failure_reason = None
                row.failed_at = None
            else:
                session.add(row)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                existing = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.idempotency_key == key))).scalar_one_or_none()
                return self._result(existing) if existing is not None else {"status": "retry"}
            if not allowed:
                if reason == "referral_reward_blocked":
                    await bus.emit(EventType.REFERRAL_REWARD_HELD, reward_public_id=row.public_reward_id, beneficiary_user_id=user_id, source_type=source_type, source_reference=source_reference)
                return self._result(row)
            row.status = ReferralRewardORM.STATUS_GRANTING
            try:
                if reward_type in {ReferralRewardORM.TYPE_EXTRA_TRIAL, ReferralRewardORM.TYPE_BONUS_DATA, ReferralRewardORM.TYPE_BONUS_DURATION}:
                    entitlement_kwargs = {
                        "user_id": user_id,
                        "source": f"{source_type}_reward",
                        "remaining_uses": int(value) if reward_type == ReferralRewardORM.TYPE_EXTRA_TRIAL else 1,
                        "expires_at": (now + timedelta(seconds=policy["expiry_seconds"])) if policy["expiry_seconds"] else None,
                        "status": "active",
                    }
                    if reward_type == ReferralRewardORM.TYPE_BONUS_DATA:
                        entitlement_kwargs["data_limit_bytes"] = int(value)
                    elif reward_type == ReferralRewardORM.TYPE_BONUS_DURATION:
                        entitlement_kwargs["duration_seconds"] = int(value)
                    entitlement = FreeTrialEntitlementORM(**entitlement_kwargs)
                    session.add(entitlement)
                    await session.flush()
                    row.entitlement_id = entitlement.id
                elif reward_type == ReferralRewardORM.TYPE_WALLET_CREDIT:
                    wallet = (await session.execute(select(WalletORM).where(WalletORM.user_id == user_id).with_for_update())).scalar_one_or_none()
                    if wallet is None:
                        wallet = WalletORM(user_id=user_id, currency=policy["wallet_currency"], balance=Decimal("0"), is_frozen=False)
                        session.add(wallet)
                        await session.flush()
                    if wallet.currency != policy["wallet_currency"] or wallet.is_frozen:
                        raise ValueError("wallet_unavailable")
                    wallet.balance = Decimal(str(wallet.balance)) + value
                    tx = TransactionORM(wallet_id=wallet.id, amount=value, currency=wallet.currency, type=TransactionORM.TYPE_BONUS, reference=row.public_reward_id, idempotency_key=key, note=f"{source_type.title()} reward")
                    session.add(tx)
                    await session.flush()
                    row.wallet_transaction_id = tx.id
                row.status = ReferralRewardORM.STATUS_GRANTED
                row.granted_at = now
                await session.flush()
                result = self._result(row)
            except Exception as exc:
                row.status = ReferralRewardORM.STATUS_FAILED
                row.failure_reason = str(exc)[:128]
                row.failed_at = now
                await session.flush()
                result = self._result(row)
        if result["status"] == ReferralRewardORM.STATUS_GRANTED:
            await bus.emit(EventType.REFERRAL_REWARD_GRANTED, reward_public_id=result["public_reward_id"], referral_id=referral_id, source_type=source_type, source_reference=source_reference, beneficiary_user_id=user_id, reward_type=reward_type)
        return result

    async def _within_limits(self, session, user_id: int, policy: dict, now: datetime):
        base = select(func.count(ReferralRewardORM.id)).where(ReferralRewardORM.beneficiary_user_id == user_id, ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED)
        lifetime = int(await session.scalar(base) or 0)
        if policy.get("global_lifetime_limit") and lifetime >= policy["global_lifetime_limit"]:
            return False, "global_lifetime_limit"
        if policy["lifetime_limit"] and lifetime >= policy["lifetime_limit"]:
            return False, "lifetime_limit"
        if policy["cooldown_seconds"]:
            latest = await session.scalar(select(func.max(ReferralRewardORM.granted_at)).where(ReferralRewardORM.beneficiary_user_id == user_id, ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED))
            if latest and now - latest < timedelta(seconds=policy["cooldown_seconds"]):
                return False, "cooldown"
        day = now - timedelta(days=1)
        daily_count = int(await session.scalar(base.where(ReferralRewardORM.granted_at >= day)) or 0)
        if policy.get("global_daily_limit") and daily_count >= policy["global_daily_limit"]:
            return False, "global_daily_limit"
        if policy["daily_limit"] and daily_count >= policy["daily_limit"]:
            return False, "daily_limit"
        week = now - timedelta(days=7)
        weekly_count = int(await session.scalar(base.where(ReferralRewardORM.granted_at >= week)) or 0)
        if policy.get("global_weekly_limit") and weekly_count >= policy["global_weekly_limit"]:
            return False, "global_weekly_limit"
        if policy["weekly_limit"] and weekly_count >= policy["weekly_limit"]:
            return False, "weekly_limit"
        month = now - timedelta(days=31)
        monthly_count = int(await session.scalar(base.where(ReferralRewardORM.granted_at >= month)) or 0)
        if policy.get("global_monthly_limit") and monthly_count >= policy["global_monthly_limit"]:
            return False, "global_monthly_limit"
        if policy["monthly_limit"] and monthly_count >= policy["monthly_limit"]:
            return False, "monthly_limit"
        return True, "eligible"

    async def release_held_reward(self, *, actor_user_id: int, reward_id: int):
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if actor is None or actor.role != "admin" or not actor.is_active:
                return Failure("permission_denied", "Admin permission required.")
            row = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.id == reward_id).with_for_update())).scalar_one_or_none()
            if row is None:
                return Failure("not_found", "Reward not found.")
            if row.status == ReferralRewardORM.STATUS_GRANTED:
                return Success(self._result(row))
            if row.status != ReferralRewardORM.STATUS_REVIEW_REQUIRED:
                return Failure("not_held", "Reward is not held for review.")
            policy = dict(row.policy_snapshot_json or {})
            policy.setdefault("revision", row.policy_revision)
            policy.setdefault("daily_limit", 0); policy.setdefault("weekly_limit", 0); policy.setdefault("monthly_limit", 0); policy.setdefault("lifetime_limit", 0); policy.setdefault("global_daily_limit", 0); policy.setdefault("global_weekly_limit", 0); policy.setdefault("global_lifetime_limit", 0); policy.setdefault("cooldown_seconds", 0); policy.setdefault("expiry_seconds", 0); policy.setdefault("wallet_currency", "MMK")
            row.status = ReferralRewardORM.STATUS_FAILED
            row.failure_reason = None
        result = await self._create_and_grant(row.referral_id, row.beneficiary_type, row.beneficiary_user_id, row.reward_type, Decimal(str(row.reward_value)), row.reward_cycle, policy, source_type=row.source_type, source_reference=row.source_reference, apply_limits=False, explicit_key=row.idempotency_key)
        if result.get("status") == ReferralRewardORM.STATUS_GRANTED:
            await bus.emit(EventType.REFERRAL_REWARD_RELEASED, reward_public_id=row.public_reward_id, actor_user_id=actor_user_id)
        return Success(result)

    async def get_reward_history(self, user_id: int, limit: int = 20):
        async with self.db.session() as session:
            rows = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.beneficiary_user_id == user_id).order_by(ReferralRewardORM.created_at.desc()).limit(max(1, min(50, limit))))).scalars().all()
            return Success([self._result(row) for row in rows])

    @staticmethod
    def _result(row):
        if row is None:
            return {"status": "retry"}
        return {"reward_id": row.id, "public_reward_id": row.public_reward_id, "referral_id": row.referral_id, "source_type": row.source_type, "source_reference": row.source_reference, "beneficiary_user_id": row.beneficiary_user_id, "beneficiary_type": row.beneficiary_type, "reward_type": row.reward_type, "reward_value": str(row.reward_value), "reward_cycle": row.reward_cycle, "status": row.status, "limit_result": row.limit_result, "failure_reason": row.failure_reason, "granted_at": row.granted_at}


def _normalize_reward_type(value: str | None) -> str:
    aliases = {
        "extra_free_trial": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "extra_trial": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "mission_trial_bonus": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "promo_free_claim": ReferralRewardORM.TYPE_EXTRA_TRIAL,
        "wallet_credit": ReferralRewardORM.TYPE_WALLET_CREDIT,
        "bonus_data": ReferralRewardORM.TYPE_BONUS_DATA,
        "bonus_duration": ReferralRewardORM.TYPE_BONUS_DURATION,
        "none": "none",
    }
    return aliases.get(str(value or "none").lower(), str(value or "none").lower())
