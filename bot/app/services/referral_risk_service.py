"""Phase 6.5 privacy-safe referral risk monitoring and review workflow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import PermissionDeniedException
from app.core.result import Failure, Success
from app.services.admin_authorization_service import AdminAuthorizationService
from app.events import EventType, bus
from database.models.audit_log import AuditLogORM
from database.models.referral import ReferralORM
from database.models.referral_reward import ReferralRewardORM, ReferralRiskEventORM
from database.models.referral_risk_observation import ReferralRiskObservationORM
from database.models.user import UserORM


class ReferralRiskService:
    """Evaluates authoritative behavioral signals without global bans."""

    SIGNAL_REFERRAL_VELOCITY = "referral_velocity_high"
    SIGNAL_QUALIFICATION_VELOCITY = "qualification_velocity_high"
    SIGNAL_REWARD_VELOCITY = "reward_velocity_high"
    SIGNAL_INVALID_VELOCITY = "invalid_referral_attempts_high"
    SIGNAL_SHORT_FIRST_SEEN = "short_first_seen_age"
    SIGNAL_RAPID_TRIAL = "rapid_trial_activation_pattern"
    SIGNAL_LIMIT_HITS = "reward_limit_hits_high"
    SIGNAL_REPEATED_REVIEW = "repeated_review_history"
    SIGNAL_SELF_REFERRAL = "self_referral_attempt"

    def __init__(
        self,
        db,
        settings_service=None,
        reward_service=None,
        referral_service=None,
        authorization_service: AdminAuthorizationService | None = None,
    ):
        self.db = db
        self.settings = settings_service
        self.reward_service = reward_service
        self.referral_service = referral_service
        self.authorization = authorization_service

    async def _setting(self, key: str, default):
        return await self.settings.get(key, default) if self.settings is not None else default

    async def _policy(self):
        return {
            "revision": int(await self._setting("referral_risk_policy_revision", 1)),
            "referral_window": max(1, int(await self._setting("referral_risk_referral_window_seconds", 300))),
            "referral_threshold": max(1, int(await self._setting("referral_risk_referral_threshold", 10))),
            "qualification_window": max(1, int(await self._setting("referral_risk_qualification_window_seconds", 600))),
            "qualification_threshold": max(1, int(await self._setting("referral_risk_qualification_threshold", 10))),
            "reward_window": max(1, int(await self._setting("referral_risk_reward_window_seconds", 3600))),
            "reward_threshold": max(1, int(await self._setting("referral_risk_reward_threshold", 5))),
            "invalid_window": max(1, int(await self._setting("referral_risk_invalid_window_seconds", 600))),
            "invalid_threshold": max(1, int(await self._setting("referral_risk_invalid_threshold", 20))),
            "auto_review": bool(await self._setting("referral_risk_auto_review", True)),
            "auto_hold": bool(await self._setting("referral_risk_auto_hold", True)),
            "auto_block": bool(await self._setting("referral_risk_auto_block", False)),
        }

    async def evaluate_behavior(self, *, user_id: int, referral_id: int | None = None, source_event: str = "manual"):
        policy = await self._policy()
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            user = await session.get(UserORM, user_id)
            if user is None:
                return Failure("not_found", "User not found.")
            since_referral = now - timedelta(seconds=policy["referral_window"])
            since_qualification = now - timedelta(seconds=policy["qualification_window"])
            since_reward = now - timedelta(seconds=policy["reward_window"])
            since_invalid = now - timedelta(seconds=policy["invalid_window"])
            referral_count = int(await session.scalar(select(func.count(ReferralRiskEventORM.id)).where(ReferralRiskEventORM.actor_user_id == user_id, ReferralRiskEventORM.event_type == "attribution", ReferralRiskEventORM.occurred_at >= since_referral)) or 0)
            qualification_count = int(await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.referrer_id == user_id, ReferralORM.qualified_at >= since_qualification)) or 0)
            reward_count = int(await session.scalar(select(func.count(ReferralRewardORM.id)).where(ReferralRewardORM.beneficiary_user_id == user_id, ReferralRewardORM.status == ReferralRewardORM.STATUS_GRANTED, ReferralRewardORM.granted_at >= since_reward)) or 0)
            invalid_count = int(await session.scalar(select(func.count(ReferralORM.id)).where(ReferralORM.referrer_id == user_id, ReferralORM.status == ReferralORM.STATUS_INVALID, ReferralORM.invalidated_at >= since_invalid)) or 0)
            review_count = int(await session.scalar(select(func.count(ReferralRiskObservationORM.id)).where(ReferralRiskObservationORM.user_id == user_id, ReferralRiskObservationORM.status.in_((ReferralRiskObservationORM.STATUS_OPEN, ReferralRiskObservationORM.STATUS_HELD, ReferralRiskObservationORM.STATUS_BLOCKED)))) or 0)
            signal_counts = {
                self.SIGNAL_REFERRAL_VELOCITY: referral_count,
                self.SIGNAL_QUALIFICATION_VELOCITY: qualification_count,
                self.SIGNAL_REWARD_VELOCITY: reward_count,
                self.SIGNAL_INVALID_VELOCITY: invalid_count,
            }
            if referral_count >= policy["referral_threshold"]:
                await self._record(session, user_id=user_id, referral_id=referral_id, signal_type=self.SIGNAL_REFERRAL_VELOCITY, count=referral_count, threshold=policy["referral_threshold"], policy=policy, now=now, source_event=source_event)
            if qualification_count >= policy["qualification_threshold"]:
                await self._record(session, user_id=user_id, referral_id=referral_id, signal_type=self.SIGNAL_QUALIFICATION_VELOCITY, count=qualification_count, threshold=policy["qualification_threshold"], policy=policy, now=now, source_event=source_event)
            if reward_count >= policy["reward_threshold"]:
                await self._record(session, user_id=user_id, referral_id=referral_id, signal_type=self.SIGNAL_REWARD_VELOCITY, count=reward_count, threshold=policy["reward_threshold"], policy=policy, now=now, source_event=source_event)
            if invalid_count >= policy["invalid_threshold"]:
                await self._record(session, user_id=user_id, referral_id=referral_id, signal_type=self.SIGNAL_INVALID_VELOCITY, count=invalid_count, threshold=policy["invalid_threshold"], policy=policy, now=now, source_event=source_event)
            age_seconds = (now - self._aware(user.first_seen_at)).total_seconds()
            if age_seconds < 86400:
                await self._record(session, user_id=user_id, referral_id=referral_id, signal_type=self.SIGNAL_SHORT_FIRST_SEEN, count=int(age_seconds), threshold=86400, policy=policy, now=now, source_event=source_event)
            if invalid_count > 0 and reward_count > 0:
                await self._record(session, user_id=user_id, referral_id=referral_id, signal_type=self.SIGNAL_LIMIT_HITS, count=invalid_count + reward_count, threshold=policy["reward_threshold"], policy=policy, now=now, source_event=source_event)
            active_signal_count = sum(value >= policy[key] for value, key in ((referral_count, "referral_threshold"), (qualification_count, "qualification_threshold"), (reward_count, "reward_threshold"), (invalid_count, "invalid_threshold")))
            if active_signal_count >= 2 and policy["auto_review"] and referral_id is not None:
                referral = await session.get(ReferralORM, referral_id, with_for_update=True)
                if referral is not None and referral.status not in {ReferralORM.STATUS_INVALID, ReferralORM.STATUS_REWARDED}:
                    referral.review_required = True
                    referral.qualification_state = ReferralORM.QUALIFICATION_REVIEW_REQUIRED
                    referral.risk_result = ReferralRiskObservationORM.LEVEL_HIGH
                    if policy["auto_hold"]:
                        referral.review_note = "risk_hold"
            result = {"user_id": user_id, "referral_id": referral_id, "signals": signal_counts, "risk_level": self._risk_level(active_signal_count), "action": ReferralRiskObservationORM.ACTION_REVIEW_REQUIRED if active_signal_count >= 2 else ReferralRiskObservationORM.ACTION_OBSERVE, "policy_revision": policy["revision"]}
        return Success(result)

    async def _record(self, session, *, user_id, referral_id, signal_type, count, threshold, policy, now, source_event):
        dedupe = f"{signal_type}:{user_id}:{now.date().isoformat()}:{policy['revision']}"
        existing = (await session.execute(select(ReferralRiskObservationORM).where(ReferralRiskObservationORM.dedupe_key == dedupe))).scalar_one_or_none()
        if existing is not None:
            return existing
        level = ReferralRiskObservationORM.LEVEL_MEDIUM if count >= threshold else ReferralRiskObservationORM.LEVEL_LOW
        row = ReferralRiskObservationORM(
            public_observation_id="OBS-" + secrets.token_urlsafe(7).replace("_", "-").replace("/", "-")[:10].upper(),
            user_id=user_id,
            referral_id=referral_id,
            signal_type=signal_type,
            risk_level=level,
            action=ReferralRiskObservationORM.ACTION_OBSERVE,
            status=ReferralRiskObservationORM.STATUS_OPEN,
            policy_revision=policy["revision"],
            safe_metadata={"count": int(count), "threshold": int(threshold), "source_event": str(source_event)[:64]},
            dedupe_key=dedupe,
            observed_at=now,
        )
        session.add(row)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return None
        await bus.emit(EventType.REFERRAL_RISK_SIGNAL_DETECTED, observation_public_id=row.public_observation_id, user_id=user_id, referral_id=referral_id, signal_type=signal_type, risk_level=level)
        return row

    async def get_review_candidates(self, *, actor_user_id: int, status="open", limit=50):
        async with self.db.session() as session:
            if not await self._authorized_operator(actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            query = select(ReferralRiskObservationORM).order_by(ReferralRiskObservationORM.observed_at.asc()).limit(max(1, min(100, int(limit))))
            if status in {"open", "resolved", "held", "blocked"}:
                query = query.where(ReferralRiskObservationORM.status == status)
            rows = list((await session.execute(query)).scalars().all())
        return Success([self._observation(row) for row in rows])

    async def resolve_review(self, *, actor_user_id: int, public_observation_id: str, decision: str, note=""):
        if decision not in {"approve", "reject", "pending", "release_reward", "block", "unblock"}:
            return Failure("invalid_decision", "Invalid review decision.")
        async with self.db.session() as session:
            actor = await session.get(UserORM, actor_user_id)
            if not await self._authorized_operator(actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            row = (await session.execute(select(ReferralRiskObservationORM).where(ReferralRiskObservationORM.public_observation_id == public_observation_id).with_for_update())).scalar_one_or_none()
            if row is None:
                return Failure("not_found", "Risk observation not found.")
            now = datetime.now(timezone.utc)
            if decision in {"block", "unblock"} and row.user_id is not None:
                user = await session.get(UserORM, row.user_id, with_for_update=True)
                if user is not None:
                    user.referral_reward_blocked = decision == "block"
                    user.referral_reward_block_reason = (note or decision)[:255] if decision == "block" else None
                    user.referral_reward_blocked_at = now if decision == "block" else None
                    user.referral_reward_blocked_by = actor_user_id if decision == "block" else None
            if decision in {"approve", "reject", "pending"} and row.referral_id is not None and self.referral_service is not None:
                referral = await session.get(ReferralORM, row.referral_id)
                public_id = referral.public_referral_id if referral else None
                if public_id:
                    # Commit this observation update first; the referral service
                    # emits the normal qualification bridge after its own commit.
                    pass
            row.resolution = decision
            row.review_note = (note or "")[:1000] or None
            row.reviewed_by = actor_user_id
            row.resolved_at = now if decision != "pending" else None
            row.status = ReferralRiskObservationORM.STATUS_OPEN if decision == "pending" else ReferralRiskObservationORM.STATUS_BLOCKED if decision == "block" else ReferralRiskObservationORM.STATUS_RESOLVED
            await session.flush()
            audit = AuditLogORM(actor_id=actor_user_id, action=f"referral.risk.{decision}", entity_type="ReferralRiskObservation", entity_id=row.id, new_value={"decision": decision, "observation_id": public_observation_id}, note=row.review_note)
            session.add(audit)
            result = self._observation(row)
        if decision == "release_reward" and row.reward_id is not None and self.reward_service is not None:
            released = await self.reward_service.release_held_reward(actor_user_id=actor_user_id, reward_id=row.reward_id)
            if released.is_failure:
                return released
        if decision in {"approve", "reject", "pending"} and row.referral_id is not None and self.referral_service is not None:
            async with self.db.session() as session:
                referral = await session.get(ReferralORM, row.referral_id)
                public_id = referral.public_referral_id if referral else None
            if public_id:
                await self.referral_service.review(actor_user_id=actor_user_id, public_referral_id=public_id, decision="approve" if decision == "approve" else "reject" if decision == "reject" else "pending", note=note)
        await bus.emit(EventType.REFERRAL_REVIEW_RESOLVED, observation_public_id=public_observation_id, decision=decision, actor_user_id=actor_user_id)
        return Success(result)

    async def user_summary(self, *, actor_user_id: int, user_id: int):
        async with self.db.session() as session:
            if not await self._authorized_operator(actor_user_id):
                return Failure("permission_denied", "Admin permission required.")
            rows = list((await session.execute(select(ReferralRiskObservationORM).where(ReferralRiskObservationORM.user_id == user_id).order_by(ReferralRiskObservationORM.observed_at.desc()).limit(50))).scalars().all())
        return Success({"user_id": user_id, "risk_level": self._risk_level(sum(row.risk_level in {"high", "critical"} for row in rows)), "open": sum(row.status == ReferralRiskObservationORM.STATUS_OPEN for row in rows), "observations": [self._observation(row) for row in rows]})

    async def _authorized_operator(self, actor_user_id: int) -> bool:
        if self.authorization is None:
            return False
        try:
            await self.authorization.require_permission_for_user(
                actor_user_id,
                "manage_referrals",
            )
        except PermissionDeniedException:
            return False
        return True

    @staticmethod
    def _risk_level(signal_count):
        if signal_count >= 4:
            return ReferralRiskObservationORM.LEVEL_CRITICAL
        if signal_count >= 2:
            return ReferralRiskObservationORM.LEVEL_HIGH
        if signal_count == 1:
            return ReferralRiskObservationORM.LEVEL_MEDIUM
        return ReferralRiskObservationORM.LEVEL_LOW

    @staticmethod
    def _aware(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    @staticmethod
    def _observation(row):
        return {"observation_id": row.public_observation_id, "user_id": row.user_id, "referral_id": row.referral_id, "reward_id": row.reward_id, "signal_type": row.signal_type, "risk_level": row.risk_level, "action": row.action, "status": row.status, "policy_revision": row.policy_revision, "safe_metadata": row.safe_metadata, "observed_at": row.observed_at, "resolution": row.resolution, "reviewed_by": row.reviewed_by}
