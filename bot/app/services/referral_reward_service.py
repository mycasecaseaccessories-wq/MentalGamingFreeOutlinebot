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


class ReferralRewardService:
    _idempotency_locks: dict[str, asyncio.Lock] = {}

    """Authoritative reward ledger and fulfillment service.

    Every beneficiary has an independent reward row.  Database uniqueness is
    deliberately relied on in addition to application checks, so retries and
    concurrent workers cannot create a second logical grant.
    """

    def __init__(self, db, settings_service):
        self.db = db
        self.settings = settings_service

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
            results.append(await self._create_and_grant(referral_id, beneficiary, user_id, reward_type, value, cycle, policy))
        return Success({"created": len(results), "rewards": results, "qualified_count": qualified_count, "cycle": cycle})

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
            "cooldown_seconds": max(0, int(await self.settings.get("referral_reward_cooldown_seconds", 3600))),
            "expiry_seconds": max(0, int(await self.settings.get("referral_reward_expiry_seconds", 2592000))),
            "wallet_currency": str(await self.settings.get("referral_reward_wallet_currency", "MMK")).upper()[:3],
        }

    async def _create_and_grant(self, referral_id, beneficiary, user_id, reward_type, value, cycle, policy):
        key = f"referral_reward:{policy['revision']}:{referral_id}:{beneficiary}:{cycle}"
        lock = self._idempotency_locks.setdefault(key, asyncio.Lock())
        async with lock:
            return await self._create_and_grant_locked(referral_id, beneficiary, user_id, reward_type, value, cycle, policy, key)

    async def _create_and_grant_locked(self, referral_id, beneficiary, user_id, reward_type, value, cycle, policy, key):
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            existing = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.idempotency_key == key).with_for_update())).scalar_one_or_none()
            if existing is not None and existing.status != ReferralRewardORM.STATUS_FAILED:
                return self._result(existing)
            allowed, reason = await self._within_limits(session, user_id, policy, now)
            row = existing or ReferralRewardORM(
                public_reward_id="RWD-" + secrets.token_urlsafe(7).replace("_", "-").replace("/", "-")[:10].upper(),
                referral_id=referral_id,
                beneficiary_user_id=user_id,
                beneficiary_type=beneficiary,
                reward_type=reward_type,
                reward_value=value,
                reward_cycle=cycle,
                policy_revision=policy["revision"],
                policy_snapshot_json={k: (str(v) if isinstance(v, Decimal) else v) for k, v in policy.items()},
                status=ReferralRewardORM.STATUS_PENDING if allowed else ReferralRewardORM.STATUS_LIMIT_REACHED,
                idempotency_key=key,
                limit_result="eligible" if allowed else reason,
                risk_result="safe",
            ) if existing is None else row
            if existing is not None:
                row.status = ReferralRewardORM.STATUS_PENDING if allowed else ReferralRewardORM.STATUS_LIMIT_REACHED
                row.limit_result = "eligible" if allowed else reason
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
                return self._result(row)
            row.status = ReferralRewardORM.STATUS_GRANTING
            try:
                if reward_type in {ReferralRewardORM.TYPE_EXTRA_TRIAL, ReferralRewardORM.TYPE_BONUS_DATA, ReferralRewardORM.TYPE_BONUS_DURATION}:
                    entitlement_kwargs = {
                        "user_id": user_id,
                        "source": "referral_reward",
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
                    tx = TransactionORM(wallet_id=wallet.id, amount=value, currency=wallet.currency, type=TransactionORM.TYPE_BONUS, reference=row.public_reward_id, idempotency_key=key, note="Referral reward")
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
            await bus.emit(EventType.REFERRAL_REWARD_GRANTED, reward_public_id=result["public_reward_id"], referral_id=referral_id, beneficiary_user_id=user_id, reward_type=reward_type)
        return result

    async def _within_limits(self, session, user_id: int, policy: dict, now: datetime):
        base = select(func.count(ReferralRewardORM.id)).where(ReferralRewardORM.beneficiary_user_id == user_id, ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED)
        lifetime = int(await session.scalar(base) or 0)
        if policy["lifetime_limit"] and lifetime >= policy["lifetime_limit"]:
            return False, "lifetime_limit"
        if policy["cooldown_seconds"]:
            latest = await session.scalar(select(func.max(ReferralRewardORM.granted_at)).where(ReferralRewardORM.beneficiary_user_id == user_id, ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED))
            if latest and now - latest < timedelta(seconds=policy["cooldown_seconds"]):
                return False, "cooldown"
        day = now - timedelta(days=1)
        if policy["daily_limit"] and int(await session.scalar(base.where(ReferralRewardORM.granted_at >= day)) or 0) >= policy["daily_limit"]:
            return False, "daily_limit"
        week = now - timedelta(days=7)
        if policy["weekly_limit"] and int(await session.scalar(base.where(ReferralRewardORM.granted_at >= week)) or 0) >= policy["weekly_limit"]:
            return False, "weekly_limit"
        month = now - timedelta(days=31)
        if policy["monthly_limit"] and int(await session.scalar(base.where(ReferralRewardORM.granted_at >= month)) or 0) >= policy["monthly_limit"]:
            return False, "monthly_limit"
        return True, "eligible"

    async def get_reward_history(self, user_id: int, limit: int = 20):
        async with self.db.session() as session:
            rows = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.beneficiary_user_id == user_id).order_by(ReferralRewardORM.created_at.desc()).limit(max(1, min(50, limit))))).scalars().all()
            return Success([self._result(row) for row in rows])

    @staticmethod
    def _result(row):
        if row is None:
            return {"status": "retry"}
        return {"reward_id": row.id, "public_reward_id": row.public_reward_id, "referral_id": row.referral_id, "beneficiary_user_id": row.beneficiary_user_id, "beneficiary_type": row.beneficiary_type, "reward_type": row.reward_type, "reward_value": str(row.reward_value), "reward_cycle": row.reward_cycle, "status": row.status, "limit_result": row.limit_result, "failure_reason": row.failure_reason, "granted_at": row.granted_at}
