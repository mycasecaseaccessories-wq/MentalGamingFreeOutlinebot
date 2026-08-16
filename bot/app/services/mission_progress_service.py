"""Atomic, event-driven mission progress and reward-claim service."""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.events import EventType, bus
from database.models.mission import MissionORM, MissionProgressEventORM, UserMissionProgressORM
from database.models.user import UserORM
from database.models.referral_reward import ReferralRewardORM
from app.services.mission_condition_service import MissionConditionService
from app.services.mission_service import MissionService


class MissionProgressService:
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, db, mission_service: MissionService, condition_service: MissionConditionService, reward_service):
        self.db = db
        self.missions = mission_service
        self.conditions = condition_service
        self.rewards = reward_service

    async def apply_event(self, *, user_id: int, event_type: str, payload: dict | None = None, source_reference: str, occurred_at: datetime | None = None, trusted: bool = True):
        if not trusted:
            return {"status": "rejected", "reason": "untrusted_event"}
        payload = payload or {}
        event_name = getattr(event_type, "value", event_type)
        occurred_at = occurred_at or datetime.now(timezone.utc)
        outputs = []
        async with self.db.session() as read_session:
            missions = (await read_session.execute(select(MissionORM).where(MissionORM.status == MissionORM.STATUS_ACTIVE, MissionORM.enabled.is_(True)))).scalars().all()
        for mission in missions:
            if not MissionService.is_available(mission, occurred_at) or not self.conditions.event_matches(mission, event_name, payload):
                continue
            period_key, period_start, period_end = self.period_for(mission, occurred_at)
            if not await self._eligible(user_id, mission):
                continue
            logical_key = f"mission_event:{mission.id}:{user_id}:{period_key}:{event_name}:{source_reference}"
            lock = self._locks.setdefault(logical_key, asyncio.Lock())
            async with lock:
                result = await self._apply_one(mission.id, user_id, event_name, payload, source_reference, occurred_at, period_key, period_start, period_end, logical_key)
            outputs.append(result)
        return {"status": "processed", "results": outputs}

    async def daily_check_in(self, user_id: int):
        return await self.apply_event(user_id=user_id, event_type=EventType.MISSION_DAILY_CHECK_IN, payload={}, source_reference="daily_check_in", trusted=True)

    async def _apply_one(self, mission_id, user_id, event_name, payload, source_reference, occurred_at, period_key, period_start, period_end, logical_key):
        complete = False
        auto_grant = False
        progress_result = None
        async with self.db.session() as session:
            mission = (await session.execute(select(MissionORM).where(MissionORM.id == mission_id))).scalar_one_or_none()
            if mission is None or not MissionService.is_available(mission, occurred_at):
                return {"status": "unavailable", "mission_id": mission_id}
            existing_event = (await session.execute(select(MissionProgressEventORM).where(MissionProgressEventORM.idempotency_key == logical_key))).scalar_one_or_none()
            if existing_event is not None:
                progress = await session.get(UserMissionProgressORM, existing_event.progress_id) if existing_event.progress_id else None
                return {"status": "duplicate", "progress": self._progress_dict(progress)}
            progress = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.user_id == user_id, UserMissionProgressORM.mission_id == mission.id, UserMissionProgressORM.period_key == period_key).with_for_update())).scalar_one_or_none()
            if progress is None:
                progress = UserMissionProgressORM(public_progress_id="PRG-" + secrets.token_urlsafe(8).replace("_", "-").replace("/", "-")[:12].upper(), user_id=user_id, mission_id=mission.id, period_key=period_key, period_start=period_start, period_end=period_end, progress_value=0, target_value_snapshot=mission.progress_target, mission_revision=mission.policy_revision, reward_type_snapshot=mission.reward_type, reward_value_snapshot=mission.reward_value, reward_expiry_seconds_snapshot=mission.reward_expiry_seconds, delivery_mode_snapshot=mission.delivery_mode, status=UserMissionProgressORM.STATUS_NOT_STARTED, idempotency_key=f"mission:{mission.id}:user:{user_id}:period:{period_key}")
                session.add(progress)
                await session.flush()
            if progress.status in {UserMissionProgressORM.STATUS_REWARD_GRANTED, UserMissionProgressORM.STATUS_EXPIRED, UserMissionProgressORM.STATUS_BLOCKED}:
                return {"status": "closed", "progress": self._progress_dict(progress)}
            delta = max(0, int(self.conditions.delta_for_event(mission, payload)))
            old_value = progress.progress_value
            progress.progress_value = min(progress.target_value_snapshot, old_value + delta)
            progress.status = UserMissionProgressORM.STATUS_IN_PROGRESS if progress.progress_value < progress.target_value_snapshot else (UserMissionProgressORM.STATUS_REWARD_PENDING if mission.delivery_mode == MissionORM.DELIVERY_MANUAL_CLAIM else UserMissionProgressORM.STATUS_COMPLETED)
            if progress.started_at is None:
                progress.started_at = occurred_at
            progress.last_source_event_at = occurred_at
            complete = progress.progress_value >= progress.target_value_snapshot
            auto_grant = complete and mission.delivery_mode == MissionORM.DELIVERY_AUTO_GRANT
            if complete and progress.completed_at is None:
                progress.completed_at = occurred_at
            event_row = MissionProgressEventORM(mission_id=mission.id, user_id=user_id, progress_id=progress.id, source_type=event_name, source_reference=str(source_reference)[:160], delta=delta, period_key=period_key, idempotency_key=logical_key, occurred_at=occurred_at, processed_at=datetime.now(timezone.utc), safe_metadata={"old_progress": old_value, "new_progress": progress.progress_value})
            session.add(event_row)
            await session.flush()
            progress_result = self._progress_dict(progress)
        await bus.emit(EventType.MISSION_PROGRESS_UPDATED, mission_public_id=mission.public_mission_id, user_id=user_id, progress=progress_result, source_type=event_name, source_reference=str(source_reference)[:160])
        if complete:
            await bus.emit(EventType.MISSION_COMPLETED, mission_public_id=mission.public_mission_id, user_id=user_id, progress_public_id=progress_result["public_progress_id"])
        if auto_grant:
            reward = await self._fulfill_reward(progress_result["id"])
            progress_result["reward"] = reward
        return {"status": "completed" if complete else "progressed", "progress": progress_result}

    async def _fulfill_reward(self, progress_id: int):
        async with self.db.session() as session:
            progress = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.id == progress_id).with_for_update())).scalar_one_or_none()
            if progress is None:
                return {"status": "missing"}
            if progress.status == UserMissionProgressORM.STATUS_REWARD_GRANTED:
                return {"status": ReferralRewardORM.STATUS_GRANTED, "public_reward_id": progress.reward_public_id, "reward_id": progress.reward_id}
            if progress.reward_type_snapshot == MissionORM.REWARD_NONE:
                progress.status = UserMissionProgressORM.STATUS_REWARD_GRANTED
                progress.reward_claimed_at = datetime.now(timezone.utc)
                await session.flush()
                return {"status": ReferralRewardORM.STATUS_GRANTED, "reward_type": MissionORM.REWARD_NONE}
            source_reference = progress.idempotency_key
            details = {"user_id": progress.user_id, "reward_type": progress.reward_type_snapshot, "reward_value": progress.reward_value_snapshot, "source_reference": source_reference, "period_key": progress.period_key, "policy_revision": progress.mission_revision, "reward_expiry_seconds": progress.reward_expiry_seconds_snapshot, "delivery_mode": progress.delivery_mode_snapshot}
        await bus.emit(EventType.MISSION_REWARD_PENDING, progress_id=progress_id, user_id=details["user_id"])
        reward = await self.rewards.grant_reward(**details)
        async with self.db.session() as session:
            progress = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.id == progress_id).with_for_update())).scalar_one_or_none()
            if progress is None:
                return reward
            if reward.get("status") == ReferralRewardORM.STATUS_GRANTED:
                progress.status = UserMissionProgressORM.STATUS_REWARD_GRANTED
                progress.reward_id = reward.get("reward_id")
                progress.reward_public_id = reward.get("public_reward_id")
                progress.reward_claimed_at = datetime.now(timezone.utc)
                await session.flush()
                await bus.emit(EventType.MISSION_REWARD_GRANTED, progress_public_id=progress.public_progress_id, reward_public_id=progress.reward_public_id, user_id=progress.user_id)
            else:
                progress.status = UserMissionProgressORM.STATUS_REWARD_PENDING
                progress.note = reward.get("failure_reason") or reward.get("status")
                await session.flush()
                await bus.emit(EventType.MISSION_REWARD_FAILED, progress_public_id=progress.public_progress_id, user_id=progress.user_id, status=reward.get("status"))
        return reward

    async def claim_reward(self, *, user_id: int, public_progress_id: str):
        lock = self._locks.setdefault(f"claim:{public_progress_id}", asyncio.Lock())
        async with lock:
            async with self.db.session() as session:
                progress = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.public_progress_id == public_progress_id, UserMissionProgressORM.user_id == user_id).with_for_update())).scalar_one_or_none()
                if progress is None:
                    return {"status": "not_found"}
                if progress.status == UserMissionProgressORM.STATUS_REWARD_GRANTED:
                    return {"status": "already_granted", "reward_public_id": progress.reward_public_id}
                if progress.status not in {UserMissionProgressORM.STATUS_REWARD_PENDING, UserMissionProgressORM.STATUS_COMPLETED}:
                    return {"status": "not_claimable", "progress": self._progress_dict(progress)}
                progress_id = progress.id
            return await self._fulfill_reward(progress_id)

    async def get_user_missions(self, user_id: int, *, include_unavailable: bool = False):
        missions = await self.missions.list_missions(active_only=True, include_unavailable=include_unavailable)
        result = []
        now = datetime.now(timezone.utc)
        async with self.db.session() as session:
            for item in missions:
                mission = (await session.execute(select(MissionORM).where(MissionORM.id == item["id"]))).scalar_one()
                period_key, _, _ = self.period_for(mission, now)
                progress = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.user_id == user_id, UserMissionProgressORM.mission_id == mission.id, UserMissionProgressORM.period_key == period_key))).scalar_one_or_none()
                entry = dict(item)
                entry["progress"] = self._progress_dict(progress)
                result.append(entry)
        return result

    async def get_history(self, user_id: int, limit: int = 50):
        async with self.db.session() as session:
            rows = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.user_id == user_id).order_by(UserMissionProgressORM.created_at.desc()).limit(max(1, min(100, limit))))).scalars().all()
            return [self._progress_dict(row) for row in rows]

    async def _eligible(self, user_id: int, mission: MissionORM) -> bool:
        if mission.eligibility_mode == "all_active_users":
            return True
        async with self.db.session() as session:
            user = await session.get(UserORM, user_id)
        if user is None or getattr(user, "is_banned", False):
            return False
        mode = mission.eligibility_mode
        if mode == "specific_role":
            return getattr(user, "role", None) == (mission.eligibility_config or {}).get("role")
        if mode == "new_users":
            cutoff = int((mission.eligibility_config or {}).get("max_age_seconds", 86400))
            return (datetime.now(timezone.utc) - self._aware(user.first_seen_at)).total_seconds() <= cutoff
        if mode == "paid_users":
            return bool(getattr(user, "has_paid_access", False))
        if mode == "free_users":
            return not bool(getattr(user, "has_paid_access", False))
        return True

    @staticmethod
    def period_for(mission: MissionORM, at: datetime):
        zone = ZoneInfo(mission.reset_timezone or "Asia/Yangon")
        local = MissionProgressService._aware(at).astimezone(zone)
        if mission.repeat_mode == MissionORM.REPEAT_ONE_TIME:
            return "one", mission.starts_at, mission.ends_at
        if mission.repeat_mode == MissionORM.REPEAT_DAILY:
            start_local = datetime.combine(local.date(), time.min, tzinfo=zone)
            return local.strftime("daily:%Y-%m-%d"), start_local.astimezone(timezone.utc), (start_local + timedelta(days=1)).astimezone(timezone.utc)
        if mission.repeat_mode == MissionORM.REPEAT_WEEKLY:
            start_local = datetime.combine(local.date() - timedelta(days=local.weekday()), time.min, tzinfo=zone)
            return local.strftime("weekly:%G-W%V"), start_local.astimezone(timezone.utc), (start_local + timedelta(days=7)).astimezone(timezone.utc)
        if mission.repeat_mode == MissionORM.REPEAT_MONTHLY:
            start_local = datetime(local.year, local.month, 1, tzinfo=zone)
            next_month = datetime(local.year + (local.month == 12), 1 if local.month == 12 else local.month + 1, 1, tzinfo=zone)
            return local.strftime("monthly:%Y-%m"), start_local.astimezone(timezone.utc), next_month.astimezone(timezone.utc)
        if mission.repeat_mode == MissionORM.REPEAT_EVENT_WINDOW:
            return f"window:{mission.starts_at or 'always'}:{mission.ends_at or 'open'}", mission.starts_at, mission.ends_at
        cooldown = max(1, int(mission.cooldown_seconds or 86400))
        bucket = int(self_timestamp(local) // cooldown)
        return f"repeatable:{bucket}", None, None

    @staticmethod
    def _aware(value):
        if value is None:
            return datetime.now(timezone.utc)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _progress_dict(progress):
        if progress is None:
            return None
        return {"id": progress.id, "public_progress_id": progress.public_progress_id, "user_id": progress.user_id, "mission_id": progress.mission_id, "period_key": progress.period_key, "period_start": progress.period_start, "period_end": progress.period_end, "progress_value": progress.progress_value, "target_value": progress.target_value_snapshot, "mission_revision": progress.mission_revision, "reward_type": progress.reward_type_snapshot, "reward_value": str(progress.reward_value_snapshot), "delivery_mode": progress.delivery_mode_snapshot, "status": progress.status, "completed_at": progress.completed_at, "reward_claimed_at": progress.reward_claimed_at, "reward_id": progress.reward_id, "reward_public_id": progress.reward_public_id, "idempotency_key": progress.idempotency_key, "note": progress.note}


def self_timestamp(value: datetime) -> float:
    return value.timestamp()
