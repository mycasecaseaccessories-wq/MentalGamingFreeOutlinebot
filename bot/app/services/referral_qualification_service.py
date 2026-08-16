from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select

from app.core.result import Failure, Success
from app.events import EventType, bus
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.order import OrderORM
from database.models.referral import ReferralORM
from database.models.referral_reward import ReferralRiskEventORM
from database.models.user import UserORM


class ReferralAbuseProtectionService:
    """Durable, privacy-respecting velocity and burst detection."""

    def __init__(self, db, settings_service):
        self.db = db
        self.settings = settings_service

    async def record_and_evaluate(self, *, referral_id: int, actor_user_id: int, occurred_at: datetime | None = None):
        now = occurred_at or datetime.now(timezone.utc)
        enabled = bool(await self.settings.get("referral_burst_detection_enabled", True))
        threshold = max(1, int(await self.settings.get("referral_burst_threshold", 10)))
        window = max(1, int(await self.settings.get("referral_burst_window_seconds", 300)))
        key = f"referral_attribution:{referral_id}"
        async with self.db.session() as session:
            existing = (await session.execute(select(ReferralRiskEventORM).where(ReferralRiskEventORM.idempotency_key == key))).scalar_one_or_none()
            if existing is None:
                session.add(ReferralRiskEventORM(referral_id=referral_id, actor_user_id=actor_user_id, event_type="attribution", occurred_at=now, idempotency_key=key, risk_result="safe"))
                await session.flush()
            since = now - timedelta(seconds=window)
            count = await session.scalar(select(func.count(ReferralRiskEventORM.id)).where(ReferralRiskEventORM.actor_user_id == actor_user_id, ReferralRiskEventORM.event_type == "attribution", ReferralRiskEventORM.occurred_at >= since))
            suspicious = enabled and int(count or 0) > threshold
            return {"result": "review_required" if suspicious else "safe", "count": int(count or 0), "threshold": threshold}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ReferralQualificationService:
    """Evaluates qualification from server-observed business facts only."""

    def __init__(self, db=None, settings_service=None, membership_service=None, reward_service=None, abuse_service=None):
        self.db = db
        self.settings = settings_service
        self.membership = membership_service
        self.reward_service = reward_service
        self.abuse = abuse_service

    async def evaluate(self, referral_id: int, *, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        async with self.db.session() as session:
            referral = (await session.execute(select(ReferralORM).where(ReferralORM.id == referral_id).with_for_update())).scalar_one_or_none()
            if referral is None:
                return Failure("not_found", "Referral not found.")
            if referral.referrer_id == referral.referred_id:
                referral.status = ReferralORM.STATUS_INVALID
                referral.qualification_state = ReferralORM.STATUS_INVALID
                referral.qualification_reason = ReferralORM.INVALID_SELF_REFERRAL
                return Failure("self_referral", "Referral is invalid.")
            if referral.status in {ReferralORM.STATUS_INVALID, ReferralORM.STATUS_CANCELLED}:
                return Success(self._result(referral))
            user = await session.get(UserORM, referral.referred_id)
            if user is None:
                return Failure("not_found", "Referred user not found.")

            min_age = max(0, int(await self.settings.get("referral_min_first_seen_age_seconds", 259200)))
            wait = max(0, int(await self.settings.get("referral_qualification_wait_seconds", 86400)))
            if min_age and now - _as_utc(user.first_seen_at) < timedelta(seconds=min_age):
                return await self._pending(session, referral, ReferralORM.QUALIFICATION_PENDING_AGE, "first_seen_age")
            if wait and now - _as_utc(referral.created_at) < timedelta(seconds=wait):
                return await self._pending(session, referral, ReferralORM.QUALIFICATION_PENDING_WAIT, "qualification_wait")

            if bool(await self.settings.get("referral_require_force_join", True)) and self.membership is not None:
                if not await self.membership.is_verified_for_current_target(user_id=user.id):
                    return await self._pending(session, referral, ReferralORM.QUALIFICATION_PENDING_FORCE_JOIN, "force_join")

            if bool(await self.settings.get("referral_require_free_trial_activation", True)):
                active = await session.scalar(select(func.count(FreeTrialClaimORM.id)).where(FreeTrialClaimORM.user_id == user.id, FreeTrialClaimORM.status == "provisioned", FreeTrialClaimORM.vpn_key_id.is_not(None)))
                if not active:
                    return await self._pending(session, referral, ReferralORM.QUALIFICATION_PENDING_FREE_TRIAL, "free_trial_activation")

            if bool(await self.settings.get("referral_require_paid_purchase", False)):
                paid = await session.scalar(select(func.count(OrderORM.id)).where(OrderORM.user_id == user.id, OrderORM.status == "paid"))
                if not paid:
                    return await self._pending(session, referral, ReferralORM.QUALIFICATION_PENDING_PAID, "paid_purchase")

            risk = {"result": "safe"}
            if self.abuse is not None:
                risk = await self.abuse.record_and_evaluate(referral_id=referral.id, actor_user_id=referral.referrer_id, occurred_at=now)
            referral.risk_result = risk["result"]
            if risk["result"] == "review_required" and bool(await self.settings.get("referral_review_suspicious", True)):
                referral.status = ReferralORM.STATUS_PENDING_QUALIFICATION
                referral.qualification_state = ReferralORM.QUALIFICATION_REVIEW_REQUIRED
                referral.qualification_reason = "suspicious_velocity"
                referral.review_required = True
                await session.flush()
                return Success(self._result(referral))

            referral.status = ReferralORM.STATUS_QUALIFIED
            referral.qualification_state = ReferralORM.STATUS_QUALIFIED
            referral.qualification_reason = None
            referral.review_required = False
            referral.qualified_at = now
            await session.flush()
            result = self._result(referral)
        await bus.emit(EventType.REFERRAL_QUALIFIED, referral_public_id=result["public_referral_id"], referred_user_id=result["referred_id"])
        if self.reward_service is not None:
            await self.reward_service.build_rewards(referral_id)
        return Success(result)

    async def _pending(self, session, referral, state: str, reason: str):
        referral.status = ReferralORM.STATUS_PENDING_QUALIFICATION
        referral.qualification_state = state
        referral.qualification_reason = reason
        referral.review_required = False
        await session.flush()
        return Success(self._result(referral))

    @staticmethod
    def _result(referral):
        return {"referral_id": referral.id, "public_referral_id": referral.public_referral_id, "referrer_id": referral.referrer_id, "referred_id": referral.referred_id, "status": referral.status, "qualification_state": referral.qualification_state, "reason": referral.qualification_reason, "risk_result": referral.risk_result}
