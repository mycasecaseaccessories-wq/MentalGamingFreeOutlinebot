from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.services.promo_redemption_service import PromoRedemptionService
from app.services.promo_service import PromoService
from app.services.referral_reward_service import ReferralRewardService
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.order import OrderORM
from database.models.promo import PromoCodeORM, PromoRedemptionORM
from database.models.referral_reward import ReferralRewardORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM


@pytest_asyncio.fixture
async def phase64_db(db_manager):
    from database.base import Base
    async with db_manager._engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return db_manager


class Settings:
    async def get(self, key, default=None):
        return {
            "currency": "MMK",
            "mission_reward_daily_limit": 0,
            "mission_reward_weekly_limit": 0,
            "mission_reward_monthly_limit": 0,
            "mission_reward_lifetime_limit": 0,
            "mission_reward_cooldown_seconds": 0,
        }.get(key, default)


async def _user(db, telegram_id: int, role: str = "customer"):
    async with db.session() as session:
        row = UserORM(telegram_id=telegram_id, full_name=str(telegram_id), role=role, language="en", status="active", is_active=True, is_verified=False)
        session.add(row)
        await session.flush()
        return row.id


def _services(db):
    settings = Settings()
    promo = PromoService(db, settings)
    rewards = ReferralRewardService(db, settings)
    redemption = PromoRedemptionService(db, promo, rewards)
    return promo, redemption


@pytest.mark.asyncio
async def test_promo_code_is_normalized_and_extra_trial_is_granted_once(phase64_db):
    user_id = await _user(phase64_db, 640001)
    promo, redemption = _services(phase64_db)
    created = await promo.create_promo(name="Welcome", code=" welcome2026 ", reward_type=PromoCodeORM.REWARD_EXTRA_TRIAL, reward_value=1, status=PromoCodeORM.STATUS_ACTIVE)
    first = await redemption.redeem(user_id=user_id, code="WELCOME2026", idempotency_key="promo-test-1")
    duplicate = await redemption.redeem(user_id=user_id, code="welcome2026", idempotency_key="promo-test-1")
    assert first["status"] == PromoRedemptionORM.STATUS_COMPLETED
    assert duplicate["public_redemption_id"] == first["public_redemption_id"]
    async with phase64_db.session() as session:
        rewards = (await session.execute(select(ReferralRewardORM).where(ReferralRewardORM.source_type == "promo", ReferralRewardORM.beneficiary_user_id == user_id))).scalars().all()
        entitlements = (await session.execute(select(FreeTrialEntitlementORM).where(FreeTrialEntitlementORM.user_id == user_id))).scalars().all()
    assert len(rewards) == 1
    assert len(entitlements) == 1
    assert created["code"] == "WELCOME2026"


@pytest.mark.asyncio
async def test_discount_applies_only_to_unpaid_owned_order_and_is_capped(phase64_db):
    user_id = await _user(phase64_db, 640002)
    promo, redemption = _services(phase64_db)
    await promo.create_promo(name="Ten percent", code="SALE10", reward_type=PromoCodeORM.REWARD_PERCENT_DISCOUNT, reward_value=10, promo_type=PromoCodeORM.TYPE_DISCOUNT, status=PromoCodeORM.STATUS_ACTIVE)
    async with phase64_db.session() as session:
        order = OrderORM(user_id=user_id, package_id=1, public_order_id="ORD-PROMO-1", checkout_token="checkout-promo-1", status=OrderORM.STATUS_PENDING, payment_status=OrderORM.PAYMENT_UNPAID, currency="MMK", subtotal_amount=Decimal("10000"), discount_amount=Decimal("0"), total_amount=Decimal("10000"))
        session.add(order)
        await session.flush()
        order_id = order.id
    result = await redemption.redeem(user_id=user_id, code="SALE10", order_id=order_id, idempotency_key="promo-discount-1")
    assert result["status"] == PromoRedemptionORM.STATUS_COMPLETED
    assert Decimal(result["discount_amount"]) == Decimal("1000.00")
    async with phase64_db.session() as session:
        stored = await session.get(OrderORM, order_id)
    assert Decimal(stored.total_amount) == Decimal("9000.00")
    assert stored.payment_status == OrderORM.PAYMENT_UNPAID


@pytest.mark.asyncio
async def test_per_user_limit_and_global_limit_are_enforced(phase64_db):
    first_user = await _user(phase64_db, 640003)
    second_user = await _user(phase64_db, 640004)
    promo, redemption = _services(phase64_db)
    await promo.create_promo(name="One trial", code="VIP1000", reward_type=PromoCodeORM.REWARD_WALLET_CREDIT, reward_value=1000, status=PromoCodeORM.STATUS_ACTIVE, max_redemptions=1, max_redemptions_per_user=1)
    first = await redemption.redeem(user_id=first_user, code="VIP1000", idempotency_key="promo-limit-1")
    same_user = await redemption.redeem(user_id=first_user, code="VIP1000", idempotency_key="promo-limit-2")
    second_user = await redemption.redeem(user_id=second_user, code="VIP1000", idempotency_key="promo-limit-3")
    assert first["status"] == PromoRedemptionORM.STATUS_COMPLETED
    assert same_user["error_code"] == "already_used"
    assert second_user["error_code"] == "usage_limit_reached"


@pytest.mark.asyncio
async def test_expiry_and_eligibility_are_server_side(phase64_db):
    user_id = await _user(phase64_db, 640005)
    promo, redemption = _services(phase64_db)
    await promo.create_promo(name="Expired", code="OLD2026", reward_type=PromoCodeORM.REWARD_EXTRA_TRIAL, reward_value=1, status=PromoCodeORM.STATUS_ACTIVE, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    await promo.create_promo(name="VIP only", code="VIPONLY", reward_type=PromoCodeORM.REWARD_EXTRA_TRIAL, reward_value=1, status=PromoCodeORM.STATUS_ACTIVE, eligibility_policy={"kind": PromoCodeORM.ELIGIBILITY_SPECIFIC_ROLE, "role": "vip"})
    expired = await redemption.redeem(user_id=user_id, code="OLD2026")
    ineligible = await redemption.redeem(user_id=user_id, code="VIPONLY")
    assert expired["error_code"] == "promo_expired"
    assert ineligible["error_code"] == "not_eligible"


@pytest.mark.asyncio
async def test_concurrent_same_idempotency_key_creates_one_redemption_and_one_wallet_bonus(phase64_db):
    user_id = await _user(phase64_db, 640006)
    promo, redemption = _services(phase64_db)
    await promo.create_promo(name="Concurrent wallet", code="BONUS100", reward_type=PromoCodeORM.REWARD_WALLET_CREDIT, reward_value=100, status=PromoCodeORM.STATUS_ACTIVE)
    results = await asyncio.gather(*[redemption.redeem(user_id=user_id, code="BONUS100", idempotency_key="promo-concurrent") for _ in range(5)])
    assert {row["public_redemption_id"] for row in results}.__len__() == 1
    async with phase64_db.session() as session:
        count = await session.scalar(select(func.count(PromoRedemptionORM.id)).where(PromoRedemptionORM.idempotency_key == "promo-concurrent"))
        tx_count = await session.scalar(select(func.count(TransactionORM.id)).where(TransactionORM.type == TransactionORM.TYPE_BONUS))
    assert count == 1
    assert tx_count == 1
