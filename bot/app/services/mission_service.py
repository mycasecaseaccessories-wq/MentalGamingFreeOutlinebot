"""Mission definition and lifecycle service for Phase 6.3."""
from __future__ import annotations

from datetime import datetime, timezone
import secrets

from sqlalchemy import select

from app.events import EventType, bus
from database.models.mission import MissionORM
from app.services.mission_condition_service import MissionConditionService


class MissionService:
    def __init__(self, db, settings_service=None):
        self.db = db
        self.settings = settings_service

    async def create_mission(self, *, name: str, description: str = "", mission_type: str, condition_config: dict, reward_type: str = MissionORM.REWARD_NONE, reward_value=0, reward_expiry_seconds: int = 0, delivery_mode: str = MissionORM.DELIVERY_AUTO_GRANT, repeat_mode: str = MissionORM.REPEAT_ONE_TIME, progress_target: int = 1, starts_at=None, ends_at=None, cooldown_seconds: int = 0, reset_timezone: str = "Asia/Yangon", eligibility_mode: str = "all_active_users", eligibility_config: dict | None = None, enabled: bool = False, sort_order: int = 0):
        self._validate_definition(mission_type, condition_config, reward_type, delivery_mode, repeat_mode, progress_target, starts_at, ends_at, cooldown_seconds)
        async with self.db.session() as session:
            mission = MissionORM(
                public_mission_id="MSN-" + secrets.token_urlsafe(8).replace("_", "-").replace("/", "-")[:12].upper(),
                name=name.strip(), description=description.strip(), mission_type=mission_type,
                condition_config=MissionConditionService.validate_condition_config(mission_type, condition_config),
                reward_type=reward_type, reward_value=reward_value, reward_expiry_seconds=int(reward_expiry_seconds),
                delivery_mode=delivery_mode, repeat_mode=repeat_mode, progress_target=int(progress_target),
                starts_at=starts_at, ends_at=ends_at, cooldown_seconds=int(cooldown_seconds), reset_timezone=reset_timezone,
                eligibility_mode=eligibility_mode, eligibility_config=eligibility_config or {}, enabled=bool(enabled),
                status=MissionORM.STATUS_ACTIVE if enabled else MissionORM.STATUS_DRAFT, sort_order=int(sort_order), policy_revision=1,
            )
            session.add(mission)
            await session.flush()
            result = self.to_dict(mission)
        if enabled:
            await bus.emit(EventType.MISSION_ACTIVATED, mission_public_id=result["public_mission_id"])
        return result

    async def update_mission(self, public_mission_id: str, **changes):
        allowed = {"name", "description", "condition_config", "reward_type", "reward_value", "reward_expiry_seconds", "delivery_mode", "repeat_mode", "progress_target", "starts_at", "ends_at", "cooldown_seconds", "reset_timezone", "eligibility_mode", "eligibility_config", "sort_order"}
        async with self.db.session() as session:
            mission = (await session.execute(select(MissionORM).where(MissionORM.public_mission_id == public_mission_id).with_for_update())).scalar_one_or_none()
            if mission is None:
                return None
            next_type = changes.get("mission_type", mission.mission_type)
            next_config = changes.get("condition_config", mission.condition_config)
            self._validate_definition(next_type, next_config, changes.get("reward_type", mission.reward_type), changes.get("delivery_mode", mission.delivery_mode), changes.get("repeat_mode", mission.repeat_mode), changes.get("progress_target", mission.progress_target), changes.get("starts_at", mission.starts_at), changes.get("ends_at", mission.ends_at), changes.get("cooldown_seconds", mission.cooldown_seconds))
            policy_change = any(key in changes for key in {"condition_config", "reward_type", "reward_value", "reward_expiry_seconds", "delivery_mode", "repeat_mode", "progress_target"})
            for key, value in changes.items():
                if key in allowed:
                    setattr(mission, key, MissionConditionService.validate_condition_config(next_type, value) if key == "condition_config" else value)
            if policy_change:
                mission.policy_revision += 1
            await session.flush()
            return self.to_dict(mission)

    async def set_status(self, public_mission_id: str, status: str):
        if status not in {MissionORM.STATUS_DRAFT, MissionORM.STATUS_ACTIVE, MissionORM.STATUS_DISABLED, MissionORM.STATUS_ENDED, MissionORM.STATUS_ARCHIVED}:
            raise ValueError("unsupported_mission_status")
        async with self.db.session() as session:
            mission = (await session.execute(select(MissionORM).where(MissionORM.public_mission_id == public_mission_id).with_for_update())).scalar_one_or_none()
            if mission is None:
                return None
            mission.status = status
            mission.enabled = status == MissionORM.STATUS_ACTIVE
            await session.flush()
            result = self.to_dict(mission)
        await bus.emit(EventType.MISSION_ACTIVATED if status == MissionORM.STATUS_ACTIVE else EventType.MISSION_EXPIRED if status == MissionORM.STATUS_ENDED else EventType.MISSION_PROGRESS_UPDATED, mission_public_id=public_mission_id, status=status)
        return result

    async def get(self, public_mission_id: str):
        async with self.db.session() as session:
            mission = (await session.execute(select(MissionORM).where(MissionORM.public_mission_id == public_mission_id))).scalar_one_or_none()
            return self.to_dict(mission) if mission else None

    async def list_missions(self, *, active_only: bool = False, include_unavailable: bool = False, now=None):
        now = now or datetime.now(timezone.utc)
        async with self.db.session() as session:
            stmt = select(MissionORM).order_by(MissionORM.sort_order.asc(), MissionORM.id.asc())
            if active_only:
                stmt = stmt.where(MissionORM.status == MissionORM.STATUS_ACTIVE, MissionORM.enabled.is_(True))
            rows = (await session.execute(stmt)).scalars().all()
        result = []
        for mission in rows:
            available = self.is_available(mission, now)
            if include_unavailable or available:
                item = self.to_dict(mission)
                item["available"] = available
                result.append(item)
        return result

    @staticmethod
    def is_available(mission: MissionORM, now: datetime) -> bool:
        if mission.status != MissionORM.STATUS_ACTIVE or not mission.enabled:
            return False
        if mission.starts_at and MissionService._aware(mission.starts_at) > MissionService._aware(now):
            return False
        if mission.ends_at and MissionService._aware(mission.ends_at) <= MissionService._aware(now):
            return False
        return True

    @staticmethod
    def _validate_definition(mission_type, condition_config, reward_type, delivery_mode, repeat_mode, target, starts_at, ends_at, cooldown):
        MissionConditionService.validate_condition_config(mission_type, condition_config)
        if reward_type not in MissionConditionService.REWARD_TYPES:
            raise ValueError("unsupported_reward_type")
        if reward_type == MissionORM.REWARD_PROMO_ENTITLEMENT:
            raise ValueError("promo_entitlement_reserved_for_phase_64")
        if delivery_mode not in {MissionORM.DELIVERY_AUTO_GRANT, MissionORM.DELIVERY_MANUAL_CLAIM}:
            raise ValueError("unsupported_delivery_mode")
        if repeat_mode not in MissionConditionService.REPEAT_MODES:
            raise ValueError("unsupported_repeat_mode")
        if int(target) <= 0 or int(cooldown) < 0:
            raise ValueError("invalid_mission_target_or_cooldown")
        if starts_at and ends_at and MissionService._aware(ends_at) <= MissionService._aware(starts_at):
            raise ValueError("mission_window_invalid")

    @staticmethod
    def _aware(value):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def to_dict(mission):
        if mission is None:
            return None
        return {"id": mission.id, "public_mission_id": mission.public_mission_id, "name": mission.name, "description": mission.description, "mission_type": mission.mission_type, "status": mission.status, "condition_config": mission.condition_config, "reward_type": mission.reward_type, "reward_value": str(mission.reward_value), "reward_expiry_seconds": mission.reward_expiry_seconds, "delivery_mode": mission.delivery_mode, "repeat_mode": mission.repeat_mode, "progress_target": mission.progress_target, "starts_at": mission.starts_at, "ends_at": mission.ends_at, "cooldown_seconds": mission.cooldown_seconds, "reset_timezone": mission.reset_timezone, "eligibility_mode": mission.eligibility_mode, "eligibility_config": mission.eligibility_config, "enabled": mission.enabled, "sort_order": mission.sort_order, "policy_revision": mission.policy_revision}
