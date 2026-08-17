from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.services.referral_analytics_service import ReferralAnalyticsService
from app.services.referral_reward_service import ReferralRewardService
from app.services.referral_risk_service import ReferralRiskService
from database.models.referral import ReferralORM
from database.models.referral_reward import ReferralRewardORM, ReferralRiskEventORM
from database.models.referral_risk_observation import ReferralRiskObservationORM
from database.models.user import UserORM
class Settings:
    def __init__(self, **values):
        self.values = {
            "referral_risk_policy_revision": 1,
            "referral_risk_referral_window_seconds": 300,
            "referral_risk_referral_threshold": 10,
            "referral_risk_qualification_window_seconds": 600,
            "referral_risk_qualification_threshold": 10,
            "referral_risk_reward_window_seconds": 3600,
            "referral_risk_reward_threshold": 5,
            "referral_risk_invalid_window_seconds": 600,
            "referral_risk_invalid_threshold": 20,
            "referral_risk_auto_review": True,
            "referral_risk_auto_hold": True,
            "referral_risk_auto_block": False,
            "referral_rewards_enabled": True,
            "referral_reward_mode": "every_n",
            "referral_required_qualified_count": 1,
            "referral_referrer_reward_type": "extra_trial",
            "referral_referrer_reward_value": 1,
            "referral_referred_reward_type": "extra_trial",
            "referral_referred_reward_value": 1,
            "referral_reward_daily_limit": 0,
            "referral_reward_weekly_limit": 0,
            "referral_reward_monthly_limit": 0,
            "referral_reward_lifetime_limit": 0,
            "referral_reward_cooldown_seconds": 0,
            "referral_reward_expiry_seconds": 3600,
            "referral_reward_wallet_currency": "MMK",
        }
        self.values.update(values)

    async def get(self, key, default=None):
        return self.values.get(key, default)


async def _user(db, telegram_id, *, first_seen_at=None):
    async with db.session() as session:
        row = UserORM(telegram_id=telegram_id, full_name=str(telegram_id), role="customer", language="en", status="active", is_active=True, is_verified=False)
        if first_seen_at is not None:
            row.first_seen_at = first_seen_at
        session.add(row)
        await session.flush()
        return row.id


async def _referral(db, referrer_id, referred_id, *, created_at=None):
    async with db.session() as session:
        row = ReferralORM(public_referral_id=f"REF-{referrer_id}-{referred_id}", referrer_id=referrer_id, referred_id=referred_id, status=ReferralORM.STATUS_PENDING_QUALIFICATION, source=ReferralORM.SOURCE_PERSONAL_LINK)
        session.add(row)
        await session.flush()
        if created_at is not None:
            row.created_at = created_at
            await session.flush()
        return row.id


@pytest_asyncio.fixture
async def phase65_db(db_manager):
    from database.base import Base

    async with db_manager._engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return db_manager


async def _admin(db, telegram_id=659900):
    async with db.session() as session:
        row = UserORM(telegram_id=telegram_id, full_name="admin", role="admin", language="en", status="active", is_active=True, is_verified=True)
        session.add(row)
        await session.flush()
        return row.id


@pytest.mark.asyncio
async def test_dashboard_is_admin_gated_and_reports_referral_funnel(phase65_db):
    admin_id = await _admin(phase65_db)
    referrer_id = await _user(phase65_db, 650001)
    referred_id = await _user(phase65_db, 650002)
    referral_id = await _referral(phase65_db, referrer_id, referred_id, created_at=datetime.now(timezone.utc) - timedelta(hours=1))
    async with phase65_db.session() as session:
        referral = await session.get(ReferralORM, referral_id)
        referral.status = ReferralORM.STATUS_QUALIFIED
        referral.qualification_state = "qualified"
        referral.qualified_at = datetime.now(timezone.utc)
        session.add(ReferralRewardORM(
            public_reward_id="RWD-PH65-1",
            referral_id=referral_id,
            source_type="referral",
            source_reference="referral",
            beneficiary_user_id=referrer_id,
            beneficiary_type=ReferralRewardORM.BENEFICIARY_REFERRER,
            reward_type=ReferralRewardORM.TYPE_EXTRA_TRIAL,
            reward_value=Decimal("1"),
            reward_cycle=1,
            policy_revision=1,
            policy_snapshot_json={},
            status=ReferralRewardORM.STATUS_GRANTED,
            idempotency_key="phase65-test-reward-1",
            granted_at=datetime.now(timezone.utc),
        ))
    service = ReferralAnalyticsService(phase65_db, Settings())
    denied = await service.dashboard(actor_user_id=referrer_id, period="last_30_days")
    assert denied.is_failure
    result = await service.dashboard(actor_user_id=admin_id, period="last_30_days")
    assert result.is_success
    dashboard = result.unwrap()
    assert dashboard["overview"]["attributed"] == 1
    assert dashboard["overview"]["qualified"] == 1
    assert dashboard["overview"]["rewards_granted"] == 1
    assert dashboard["funnel"]["rates"]["attribution_to_qualification_percent"] == 100.0


@pytest.mark.asyncio
async def test_risk_velocity_observation_is_deduplicated_and_reviewable(phase65_db):
    admin_id = await _admin(phase65_db, 659901)
    user_id = await _user(phase65_db, 650003, first_seen_at=datetime.now(timezone.utc))
    settings = Settings(referral_risk_referral_threshold=1, referral_risk_referral_window_seconds=3600)
    async with phase65_db.session() as session:
        session.add(ReferralRiskEventORM(
            actor_user_id=user_id,
            event_type="attribution",
            occurred_at=datetime.now(timezone.utc),
            idempotency_key="phase65-risk-event-1",
            safe_metadata={"source": "server"},
        ))
    service = ReferralRiskService(phase65_db, settings)
    first = await service.evaluate_behavior(user_id=user_id, source_event="referral.attributed")
    second = await service.evaluate_behavior(user_id=user_id, source_event="referral.attributed")
    assert first.is_success and second.is_success
    async with phase65_db.session() as session:
        observations = list((await session.execute(select(ReferralRiskObservationORM).where(ReferralRiskObservationORM.user_id == user_id))).scalars().all())
    assert len(observations) >= 1
    assert len({row.dedupe_key for row in observations}) == len(observations)
    queue = await service.get_review_candidates(actor_user_id=admin_id)
    assert queue.is_success


@pytest.mark.asyncio
async def test_referral_reward_block_holds_only_referral_reward(phase65_db):
    referrer_id = await _user(phase65_db, 650004)
    referred_id = await _user(phase65_db, 650005)
    referral_id = await _referral(phase65_db, referrer_id, referred_id)
    async with phase65_db.session() as session:
        referrer = await session.get(UserORM, referrer_id)
        referrer.referral_reward_blocked = True
        referrer.referral_reward_block_reason = "manual_review"
        referral = await session.get(ReferralORM, referral_id)
        referral.status = ReferralORM.STATUS_QUALIFIED
        referral.qualification_state = "qualified"
    result = await ReferralRewardService(phase65_db, Settings()).build_rewards(referral_id)
    assert result.is_success
    async with phase65_db.session() as session:
        rows = list((await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.referral_id == referral_id))).scalars().all())
    referrer_rows = [row for row in rows if row.beneficiary_user_id == referrer_id]
    referred_rows = [row for row in rows if row.beneficiary_user_id == referred_id]
    assert referrer_rows and all(row.status == ReferralRewardORM.STATUS_REVIEW_REQUIRED for row in referrer_rows)
    assert referred_rows and all(row.status == ReferralRewardORM.STATUS_GRANTED for row in referred_rows)
