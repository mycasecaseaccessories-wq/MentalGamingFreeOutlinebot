from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.result import Success
from app.services.free_trial_abuse_service import FreeTrialAbuseProtectionService
from app.services.free_trial_upgrade_service import (
    DATA_ADDON,
    DURATION_EXTENSION,
    PAID_PLAN_CONVERSION,
    FreeTrialUpgradeService,
)
from database.connection import DatabaseManager
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.free_trial_upgrade import FreeTrialRestrictionORM, FreeTrialUpgradeOfferORM, FreeTrialUpgradeORM
from database.models.order import OrderORM
from database.models.package import PackageORM
from database.models.user import UserORM
from database.models.vpn_key import VPNKeyORM


class FakeDataLimit:
    def __init__(self, db):
        self.db = db
        self.calls = []

    async def apply_for_key(self, **kwargs):
        self.calls.append(kwargs)
        async with self.db.session() as session:
            key = await session.get(VPNKeyORM, kwargs["key_id"], with_for_update=True)
            key.data_limit_bytes = kwargs["requested_limit_bytes"]
            key.used_bytes = 123
        return Success({"limit_bytes": kwargs["requested_limit_bytes"]})


class FakeLifecycle:
    def __init__(self, db):
        self.db = db
        self.calls = []

    async def extend_key_to(self, **kwargs):
        self.calls.append(kwargs)
        async with self.db.session() as session:
            key = await session.get(VPNKeyORM, kwargs["key_id"], with_for_update=True)
            key.expires_at = kwargs["target_expires_at"]
        return Success({"expires_at": kwargs["target_expires_at"]})


async def _seed(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'phase56.db'}")
    await db.init()
    async with db.session() as session:
        user = UserORM(telegram_id=995601, full_name="Phase 5.6 User", role="customer", language="en", status="active", is_active=True)
        admin = UserORM(telegram_id=995602, full_name="Phase 5.6 Admin", role="admin", language="en", status="active", is_active=True)
        package = PackageORM(package_type="free_trial", name="Free Trial", description="test", price=0, currency="MMK", duration_days=1, data_limit_gb=0.5, max_devices=1, is_active=True, sort_order=1)
        target = PackageORM(package_type="paid", name="Paid Plan", description="test", price=1000, currency="MMK", duration_days=30, data_limit_gb=10, max_devices=2, is_active=True, sort_order=2)
        session.add_all([user, admin, package, target])
        await session.flush()
        key = VPNKeyORM(user_id=user.id, server_id=1, outline_key_id=101, access_url="ss://redacted", name="Trial", data_limit_bytes=500, used_bytes=123, device_limit=1, package_id=package.id, key_type="free_trial", status="active", is_active=True, activated_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        session.add(key)
        await session.flush()
        claim = FreeTrialClaimORM(user_id=user.id, package_id=package.id, idempotency_key="claim-56", period_start=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0), source="daily_free", status="active", data_limit_bytes=500, duration_seconds=86400, device_limit=1, policy_snapshot_json="{}", claimed_at=datetime.now(timezone.utc), accepted_at=datetime.now(timezone.utc), vpn_key_id=key.id)
        session.add(claim)
        offer_data = FreeTrialUpgradeOfferORM(public_offer_id="offer-data", name="+1 GB", upgrade_type=DATA_ADDON, price=Decimal("1000"), currency="MMK", additional_data_bytes=1000, additional_duration_seconds=0, enabled=True, sort_order=1)
        offer_duration = FreeTrialUpgradeOfferORM(public_offer_id="offer-duration", name="+7 days", upgrade_type=DURATION_EXTENSION, price=Decimal("500"), currency="MMK", additional_data_bytes=0, additional_duration_seconds=604800, enabled=True, sort_order=2)
        offer_conversion = FreeTrialUpgradeOfferORM(public_offer_id="offer-convert", name="Paid Plan", upgrade_type=PAID_PLAN_CONVERSION, price=Decimal("1000"), currency="MMK", additional_data_bytes=0, additional_duration_seconds=0, target_package_id=target.id, enabled=True, sort_order=3)
        session.add_all([offer_data, offer_duration, offer_conversion])
        await session.flush()
        return db, user.id, admin.id, key.id, offer_data.id, offer_duration.id, offer_conversion.id, target.id


@pytest.mark.asyncio
async def test_upgrade_order_is_idempotent_and_requires_payment(tmp_path):
    db, user_id, _, key_id, offer_id, _, _, _ = await _seed(tmp_path)
    service = FreeTrialUpgradeService(db, data_limit_service=FakeDataLimit(db))
    first = await service.create_upgrade_order(user_id=user_id, vpn_key_id=key_id, offer_id=offer_id, idempotency_key="upgrade-56")
    replay = await service.create_upgrade_order(user_id=user_id, vpn_key_id=key_id, offer_id=offer_id, idempotency_key="upgrade-56")
    assert first.is_success and replay.is_success
    assert first.unwrap()["order_id"] == replay.unwrap()["order_id"]
    blocked = await service.fulfill_paid_upgrade(order_id=first.unwrap()["order_id"])
    assert blocked.is_failure and blocked.error.code == "payment_pending"
    await db.close()


@pytest.mark.asyncio
async def test_paid_data_upgrade_applies_once_and_preserves_usage(tmp_path):
    db, user_id, _, key_id, offer_id, _, _, _ = await _seed(tmp_path)
    fake_data = FakeDataLimit(db)
    service = FreeTrialUpgradeService(db, data_limit_service=fake_data)
    created = await service.create_upgrade_order(user_id=user_id, vpn_key_id=key_id, offer_id=offer_id, idempotency_key="upgrade-data")
    order_id = created.unwrap()["order_id"]
    async with db.session() as session:
        order = await session.get(OrderORM, order_id)
        order.payment_status = OrderORM.PAYMENT_PAID
        order.status = OrderORM.STATUS_PAID
    result = await service.fulfill_paid_upgrade(order_id=order_id)
    replay = await service.fulfill_paid_upgrade(order_id=order_id)
    assert result.is_success and replay.is_success
    assert len(fake_data.calls) == 1
    async with db.session() as session:
        key = await session.get(VPNKeyORM, key_id)
        upgrade = (await session.execute(select(FreeTrialUpgradeORM).where(FreeTrialUpgradeORM.order_id == order_id))).scalar_one()
        assert key.data_limit_bytes == 1500
        assert key.used_bytes == 123
        assert upgrade.status == "fulfilled"
    await db.close()


@pytest.mark.asyncio
async def test_duration_upgrade_and_paid_conversion_preserve_origin(tmp_path):
    db, user_id, _, key_id, _, duration_offer_id, conversion_offer_id, target_package_id = await _seed(tmp_path)
    fake_lifecycle = FakeLifecycle(db)
    service = FreeTrialUpgradeService(db, lifecycle_service=fake_lifecycle)
    duration = await service.create_upgrade_order(user_id=user_id, vpn_key_id=key_id, offer_id=duration_offer_id, idempotency_key="upgrade-duration")
    async with db.session() as session:
        order = await session.get(OrderORM, duration.unwrap()["order_id"])
        order.payment_status = OrderORM.PAYMENT_PAID
        order.status = OrderORM.STATUS_PAID
    assert (await service.fulfill_paid_upgrade(order_id=duration.unwrap()["order_id"])).is_success
    conversion = await service.create_upgrade_order(user_id=user_id, vpn_key_id=key_id, offer_id=conversion_offer_id, idempotency_key="upgrade-convert")
    async with db.session() as session:
        order = await session.get(OrderORM, conversion.unwrap()["order_id"])
        order.payment_status = OrderORM.PAYMENT_PAID
        order.status = OrderORM.STATUS_PAID
    assert (await service.fulfill_paid_upgrade(order_id=conversion.unwrap()["order_id"])).is_success
    async with db.session() as session:
        key = await session.get(VPNKeyORM, key_id)
        claim = (await session.execute(select(FreeTrialClaimORM).where(FreeTrialClaimORM.vpn_key_id == key_id))).scalar_one()
        assert key.key_type == "paid"
        assert key.package_id == target_package_id
        assert claim.source == "daily_free"
        assert key.activated_at is not None
    await db.close()


@pytest.mark.asyncio
async def test_trial_specific_abuse_block_does_not_change_paid_account_state(tmp_path):
    db, user_id, admin_id, *_ = await _seed(tmp_path)
    abuse = FreeTrialAbuseProtectionService(db)
    assert (await abuse.block_user(actor_user_id=admin_id, user_id=user_id, reason="abuse")).is_success
    blocked = await abuse.evaluate_claim(user_id=user_id)
    assert blocked.is_failure and blocked.error.code == "free_trial_restricted"
    async with db.session() as session:
        row = (await session.execute(select(FreeTrialRestrictionORM).where(FreeTrialRestrictionORM.user_id == user_id))).scalar_one()
        assert row.blocked is True
    assert (await abuse.unblock_user(actor_user_id=admin_id, user_id=user_id)).is_success
    assert (await abuse.evaluate_claim(user_id=user_id)).is_success
    await db.close()
