from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, func

from app.services.mission_condition_service import MissionConditionService
from app.services.mission_progress_service import MissionProgressService
from app.services.mission_service import MissionService
from app.services.referral_reward_service import ReferralRewardService
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.mission import MissionORM, MissionProgressEventORM, UserMissionProgressORM
from database.models.referral_reward import ReferralRewardORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM


@pytest_asyncio.fixture
async def phase63_db(db_manager):
    from database.base import Base
    async with db_manager._engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return db_manager


class Settings:
    async def get(self, key, default=None):
        return {
            "mission_reward_daily_limit": 0,
            "mission_reward_weekly_limit": 0,
            "mission_reward_monthly_limit": 0,
            "mission_reward_lifetime_limit": 0,
            "mission_reward_cooldown_seconds": 0,
            "currency": "MMK",
        }.get(key, default)


async def _user(db, telegram_id):
    async with db.session() as session:
        user = UserORM(telegram_id=telegram_id, full_name=str(telegram_id), role="customer", language="en", status="active", is_active=True, is_verified=False)
        session.add(user)
        await session.flush()
        return user.id


def _services(db):
    settings = Settings()
    condition = MissionConditionService()
    missions = MissionService(db, settings)
    rewards = ReferralRewardService(db, settings)
    progress = MissionProgressService(db, missions, condition, rewards)
    return missions, progress


@pytest.mark.asyncio
async def test_mission_condition_validation_rejects_executable_config():
    with pytest.raises(ValueError, match="executable"):
        MissionConditionService.validate_condition_config(MissionORM.TYPE_CUSTOM_EVENT, {"event_name": "mission.daily_check_in", "value": "lambda: 1"})


@pytest.mark.asyncio
async def test_custom_event_progress_is_source_idempotent_and_auto_grants_entitlement(phase63_db):
    user_id = await _user(phase63_db, 630001)
    missions, progress = _services(phase63_db)
    mission = await missions.create_mission(name="Two trusted actions", mission_type=MissionORM.TYPE_CUSTOM_EVENT, condition_config={"event_name": "mission.trusted_action"}, reward_type=MissionORM.REWARD_EXTRA_TRIAL, reward_value=1, progress_target=2, enabled=True)
    first = await progress.apply_event(user_id=user_id, event_type="mission.trusted_action", payload={}, source_reference="action-1")
    duplicate = await progress.apply_event(user_id=user_id, event_type="mission.trusted_action", payload={}, source_reference="action-1")
    second = await progress.apply_event(user_id=user_id, event_type="mission.trusted_action", payload={}, source_reference="action-2")
    assert first["status"] == "processed"
    assert duplicate["results"][0]["status"] == "duplicate"
    assert second["results"][0]["status"] == "completed"
    async with phase63_db.session() as session:
        progress_row = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.user_id == user_id, UserMissionProgressORM.mission_id == mission["id"])) ).scalar_one()
        event_count = await session.scalar(select(func.count(MissionProgressEventORM.id)).where(MissionProgressEventORM.user_id == user_id))
        reward = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.source_type == "mission", ReferralRewardORM.beneficiary_user_id == user_id))).scalar_one()
        entitlement = await session.get(FreeTrialEntitlementORM, reward.entitlement_id)
    assert progress_row.status == UserMissionProgressORM.STATUS_REWARD_GRANTED
    assert progress_row.progress_value == 2
    assert event_count == 2
    assert reward.status == ReferralRewardORM.STATUS_GRANTED
    assert entitlement is not None
    assert entitlement.remaining_uses == 1


@pytest.mark.asyncio
async def test_manual_wallet_claim_is_idempotent_under_concurrency(phase63_db):
    user_id = await _user(phase63_db, 630002)
    missions, progress = _services(phase63_db)
    mission = await missions.create_mission(name="Manual wallet task", mission_type=MissionORM.TYPE_CUSTOM_EVENT, condition_config={"event_name": "mission.wallet_task"}, reward_type=MissionORM.REWARD_WALLET_CREDIT, reward_value=Decimal("25"), delivery_mode=MissionORM.DELIVERY_MANUAL_CLAIM, enabled=True)
    applied = await progress.apply_event(user_id=user_id, event_type="mission.wallet_task", payload={}, source_reference="wallet-task-1")
    public_progress_id = applied["results"][0]["progress"]["public_progress_id"]
    results = await asyncio.gather(*[progress.claim_reward(user_id=user_id, public_progress_id=public_progress_id) for _ in range(4)])
    assert all(result["status"] in {ReferralRewardORM.STATUS_GRANTED, "already_granted"} for result in results)
    async with phase63_db.session() as session:
        rewards = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.source_type == "mission", ReferralRewardORM.beneficiary_user_id == user_id))).scalars().all()
        transactions = (await session.execute(select(TransactionORM).where(TransactionORM.type == TransactionORM.TYPE_BONUS))).scalars().all()
        stored = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.public_progress_id == public_progress_id))).scalar_one()
    assert len(rewards) == 1
    assert len(transactions) == 1
    assert stored.status == UserMissionProgressORM.STATUS_REWARD_GRANTED


@pytest.mark.asyncio
async def test_daily_period_creates_new_progress_without_destructive_reset(phase63_db):
    user_id = await _user(phase63_db, 630003)
    missions, progress = _services(phase63_db)
    mission = await missions.create_mission(name="Daily check-in", mission_type=MissionORM.TYPE_DAILY_CHECK_IN, condition_config={}, reward_type=MissionORM.REWARD_NONE, repeat_mode=MissionORM.REPEAT_DAILY, enabled=True)
    day_one = datetime(2026, 8, 16, 5, 0, tzinfo=timezone.utc)
    day_two = day_one + timedelta(days=1)
    first = await progress.apply_event(user_id=user_id, event_type="mission.daily_check_in", payload={}, source_reference="daily_check_in", occurred_at=day_one)
    second = await progress.apply_event(user_id=user_id, event_type="mission.daily_check_in", payload={}, source_reference="daily_check_in", occurred_at=day_two)
    assert first["results"][0]["status"] == "completed"
    assert second["results"][0]["status"] == "completed"
    async with phase63_db.session() as session:
        rows = (await session.execute(select(UserMissionProgressORM).where(UserMissionProgressORM.user_id == user_id, UserMissionProgressORM.mission_id == mission["id"])) ).scalars().all()
    assert len(rows) == 2
    assert {row.period_key for row in rows} == {"daily:2026-08-16", "daily:2026-08-17"}
