from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from sqlalchemy import func, select
from app.services.free_trial_claim_service import FreeTrialClaimService
from database.connection import DatabaseManager
from database.models.free_trial_claim import FreeTrialClaimORM
from database.models.free_trial_entitlement import FreeTrialEntitlementORM
from database.models.package import PackageORM
from database.models.user import UserORM

def _url(tmp_path: Path) -> str: return f"sqlite+aiosqlite:///{tmp_path / 'phase53.db'}"
async def _seed(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path)); await db.init()
    async with db.session() as session:
        user = UserORM(telegram_id=995301, full_name="Phase 5.3 User", role="customer", language="en", status="active", is_active=True)
        package = PackageORM(package_type="free_trial", name="Free Trial", description="test", price=0, currency="USD", duration_days=1, data_limit_gb=1, max_devices=1, is_active=True, sort_order=1)
        session.add_all([user, package]); await session.flush(); return db, user.id, package.id
POLICY={"free_trial_enabled":True,"free_trial_normal_claims_per_period":1,"free_trial_daily_data_cap_bytes":1024,"free_trial_data_per_claim_bytes":1024,"free_trial_duration_seconds":86400,"free_trial_device_limit":1,"free_trial_extra_claims_enabled":True}
@pytest.mark.asyncio
async def test_concurrent_daily_clicks_accept_only_one_claim(tmp_path):
    db,user_id,package_id=await _seed(tmp_path); service=FreeTrialClaimService(db)
    results=await asyncio.gather(*(service.accept_claim(user_id=user_id,package_id=package_id,idempotency_key=f"click-{i}",policy=POLICY) for i in range(2)),return_exceptions=True)
    successful=[r for r in results if not isinstance(r,Exception) and r.is_success]; assert len(successful)==1
    async with db.session() as s: assert await s.scalar(select(func.count(FreeTrialClaimORM.id)))==1
    await db.close()
@pytest.mark.asyncio
async def test_same_idempotency_key_replays_one_claim(tmp_path):
    db,user_id,package_id=await _seed(tmp_path); service=FreeTrialClaimService(db)
    a=await service.accept_claim(user_id=user_id,package_id=package_id,idempotency_key="same",policy=POLICY); b=await service.accept_claim(user_id=user_id,package_id=package_id,idempotency_key="same",policy=POLICY)
    assert a.is_success and b.is_success and a.unwrap().id==b.unwrap().id; await db.close()
@pytest.mark.asyncio
async def test_extra_entitlement_refunds_on_cancel(tmp_path):
    db,user_id,package_id=await _seed(tmp_path)
    async with db.session() as s: s.add(FreeTrialEntitlementORM(user_id=user_id,source="referral",remaining_uses=1,status="active",data_limit_bytes=512,duration_seconds=3600,device_limit=1))
    service=FreeTrialClaimService(db); policy=dict(POLICY,free_trial_normal_claims_per_period=0,free_trial_daily_data_cap_bytes=0)
    r=await service.accept_claim(user_id=user_id,package_id=package_id,idempotency_key="extra",policy=policy); assert r.is_success and r.unwrap().source=="extra_entitlement"
    await service.cancel_claim(claim_id=r.unwrap().id,reason="provisioning_failed")
    async with db.session() as s: assert (await s.execute(select(FreeTrialEntitlementORM))).scalar_one().remaining_uses==1
    await db.close()
