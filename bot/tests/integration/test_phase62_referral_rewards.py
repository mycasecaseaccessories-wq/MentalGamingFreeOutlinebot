from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.services.referral_qualification_service import ReferralAbuseProtectionService, ReferralQualificationService
from app.services.referral_reward_service import ReferralRewardService
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.referral import ReferralORM
from database.models.referral_reward import ReferralRewardORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM


@pytest_asyncio.fixture
async def phase62_db(db_manager):
    from database.base import Base
    async with db_manager._engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return db_manager


class Settings:
    def __init__(self, **values):
        self.values = {
            "referral_min_first_seen_age_seconds": 0,
            "referral_qualification_wait_seconds": 0,
            "referral_require_force_join": False,
            "referral_require_free_trial_activation": False,
            "referral_require_paid_purchase": False,
            "referral_burst_detection_enabled": True,
            "referral_burst_threshold": 10,
            "referral_burst_window_seconds": 300,
            "referral_review_suspicious": True,
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
    async with db.session() as s:
        row = UserORM(telegram_id=telegram_id, full_name=str(telegram_id), role="customer", language="en", status="active", is_active=True, is_verified=False)
        if first_seen_at is not None:
            row.first_seen_at = first_seen_at
        s.add(row)
        await s.flush()
        return row.id


async def _referral(db, referrer_id, referred_id, *, created_at=None):
    async with db.session() as s:
        row = ReferralORM(public_referral_id=f"REF-{referrer_id}-{referred_id}", referrer_id=referrer_id, referred_id=referred_id, status=ReferralORM.STATUS_PENDING_QUALIFICATION, source=ReferralORM.SOURCE_PERSONAL_LINK)
        s.add(row)
        await s.flush()
        if created_at is not None:
            row.created_at = created_at
            await s.flush()
        return row.id


@pytest.mark.asyncio
async def test_first_seen_age_is_server_observed_and_wait_recheck_is_idempotent(phase62_db):
    now = datetime.now(timezone.utc)
    referrer = await _user(phase62_db, 620001, first_seen_at=now - timedelta(days=10))
    referred = await _user(phase62_db, 620002, first_seen_at=now - timedelta(hours=1))
    referral_id = await _referral(phase62_db, referrer, referred, created_at=now - timedelta(days=2))
    service = ReferralQualificationService(phase62_db, Settings(referral_min_first_seen_age_seconds=3 * 86400))
    first = await service.evaluate(referral_id, now=now)
    assert first.unwrap()["qualification_state"] == ReferralORM.QUALIFICATION_PENDING_AGE
    async with phase62_db.session() as s:
        user = await s.get(UserORM, referred)
        user.first_seen_at = now - timedelta(days=4)
    second = await service.evaluate(referral_id, now=now)
    third = await service.evaluate(referral_id, now=now)
    assert second.unwrap()["status"] == ReferralORM.STATUS_QUALIFIED
    assert third.unwrap()["status"] == ReferralORM.STATUS_QUALIFIED


@pytest.mark.asyncio
async def test_self_referral_never_qualifies(phase62_db):
    user = await _user(phase62_db, 620003)
    referral_id = await _referral(phase62_db, user, user)
    result = await ReferralQualificationService(phase62_db, Settings()).evaluate(referral_id)
    assert result.is_failure
    async with phase62_db.session() as s:
        row = await s.get(ReferralORM, referral_id)
        assert row.status == ReferralORM.STATUS_INVALID


@pytest.mark.asyncio
async def test_burst_detection_holds_referral_for_review(phase62_db):
    user = await _user(phase62_db, 620004)
    settings = Settings(referral_burst_threshold=1)
    abuse = ReferralAbuseProtectionService(phase62_db, settings)
    first = await _referral(phase62_db, user, await _user(phase62_db, 620005))
    second = await _referral(phase62_db, user, await _user(phase62_db, 620006))
    await abuse.record_and_evaluate(referral_id=first, actor_user_id=user)
    result = await abuse.record_and_evaluate(referral_id=second, actor_user_id=user)
    assert result["result"] == "review_required"


@pytest.mark.asyncio
async def test_extra_trial_reward_is_idempotent_and_separate_by_beneficiary(phase62_db):
    referrer = await _user(phase62_db, 620007)
    referred = await _user(phase62_db, 620008)
    referral_id = await _referral(phase62_db, referrer, referred)
    async with phase62_db.session() as s:
        row = await s.get(ReferralORM, referral_id)
        row.status = ReferralORM.STATUS_QUALIFIED
        row.qualified_at = datetime.now(timezone.utc)
    rewards = ReferralRewardService(phase62_db, Settings())
    first = await rewards.build_rewards(referral_id)
    second = await rewards.build_rewards(referral_id)
    assert first.is_success and second.is_success
    async with phase62_db.session() as s:
        rows = (await s.execute(select(ReferralRewardORM).where(ReferralRewardORM.referral_id == referral_id))).scalars().all()
        entitlements = (await s.execute(select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.source == "referral_reward"))).scalars().all()
    assert len(rows) == 2
    assert all(row.status == ReferralRewardORM.STATUS_GRANTED for row in rows)
    assert len(entitlements) == 2


@pytest.mark.asyncio
async def test_wallet_reward_writes_one_bonus_ledger_entry(phase62_db):
    referrer = await _user(phase62_db, 620009)
    referred = await _user(phase62_db, 620010)
    referral_id = await _referral(phase62_db, referrer, referred)
    async with phase62_db.session() as s:
        row = await s.get(ReferralORM, referral_id)
        row.status = ReferralORM.STATUS_QUALIFIED
    settings = Settings(referral_referrer_reward_type="wallet_credit", referral_referrer_reward_value=Decimal("100"), referral_referred_reward_type="wallet_credit", referral_referred_reward_value=Decimal("50"))
    rewards = ReferralRewardService(phase62_db, settings)
    await rewards.build_rewards(referral_id)
    await rewards.build_rewards(referral_id)
    async with phase62_db.session() as s:
        txs = (await s.execute(select(TransactionORM).where(TransactionORM.type == TransactionORM.TYPE_BONUS))).scalars().all()
    assert len(txs) == 2
    assert {Decimal(str(tx.amount)) for tx in txs} == {Decimal("100"), Decimal("50")}


@pytest.mark.asyncio
async def test_bonus_data_and_duration_rewards_use_entitlement_fields(phase62_db):
    referrer = await _user(phase62_db, 620011)
    referred = await _user(phase62_db, 620012)
    referral_id = await _referral(phase62_db, referrer, referred)
    async with phase62_db.session() as s:
        row = await s.get(ReferralORM, referral_id)
        row.status = ReferralORM.STATUS_QUALIFIED
    settings = Settings(referral_referrer_reward_type="bonus_data", referral_referrer_reward_value=1024, referral_referred_reward_type="bonus_duration", referral_referred_reward_value=3600)
    result = await ReferralRewardService(phase62_db, settings).build_rewards(referral_id)
    assert result.is_success
    async with phase62_db.session() as s:
        rows = (await s.execute(select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.source == "referral_reward").order_by(FreeTrialEntitlementORM.id.desc()).limit(2))).scalars().all()
    assert {row.data_limit_bytes for row in rows} == {1024, None}
    assert {row.duration_seconds for row in rows} == {3600, None}


@pytest.mark.asyncio
async def test_concurrent_reward_builds_do_not_duplicate_cycles(phase62_db):
    import asyncio
    referrer = await _user(phase62_db, 620013)
    referred = await _user(phase62_db, 620014)
    referral_id = await _referral(phase62_db, referrer, referred)
    async with phase62_db.session() as s:
        row = await s.get(ReferralORM, referral_id)
        row.status = ReferralORM.STATUS_QUALIFIED
    results = await asyncio.gather(*[ReferralRewardService(phase62_db, Settings()).build_rewards(referral_id) for _ in range(4)], return_exceptions=True)
    assert all(not isinstance(result, Exception) for result in results), repr(results)
    async with phase62_db.session() as s:
        rows = (await s.execute(select(ReferralRewardORM).where(ReferralRewardORM.referral_id == referral_id))).scalars().all()
    assert len(rows) == 2
    assert len({row.idempotency_key for row in rows}) == 2


@pytest.mark.asyncio
async def test_daily_reward_limit_is_ledgered_without_invalidating_qualification(phase62_db):
    referrer = await _user(phase62_db, 620015)
    referred_a = await _user(phase62_db, 620016)
    referred_b = await _user(phase62_db, 620017)
    first_id = await _referral(phase62_db, referrer, referred_a)
    second_id = await _referral(phase62_db, referrer, referred_b)
    async with phase62_db.session() as s:
        first = await s.get(ReferralORM, first_id)
        second = await s.get(ReferralORM, second_id)
        first.status = ReferralORM.STATUS_QUALIFIED
        second.status = ReferralORM.STATUS_QUALIFIED
    settings = Settings(referral_reward_daily_limit=1)
    service = ReferralRewardService(phase62_db, settings)
    await service.build_rewards(first_id)
    await service.build_rewards(second_id)
    async with phase62_db.session() as s:
        rows = (await s.execute(select(ReferralRewardORM).where(ReferralRewardORM.beneficiary_user_id == referrer))).scalars().all()
        second_referral = await s.get(ReferralORM, second_id)
    assert {row.status for row in rows} == {ReferralRewardORM.STATUS_GRANTED, ReferralRewardORM.STATUS_LIMIT_REACHED}
    assert second_referral.status == ReferralORM.STATUS_QUALIFIED
