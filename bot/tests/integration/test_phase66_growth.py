from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.growth_reward_service import GrowthRewardService
from database.models.referral_reward import ReferralRewardORM


def test_phase66_reward_types_are_canonical():
    assert GrowthRewardService.normalize_reward_type("extra_free_trial") == ReferralRewardORM.TYPE_EXTRA_TRIAL
    assert GrowthRewardService.normalize_reward_type("mission_trial_bonus") == ReferralRewardORM.TYPE_EXTRA_TRIAL
    assert GrowthRewardService.normalize_reward_type("promo_free_claim") == ReferralRewardORM.TYPE_EXTRA_TRIAL
    assert GrowthRewardService.normalize_reward_type("bonus_data") == ReferralRewardORM.TYPE_BONUS_DATA


def test_phase66_reward_formatter_uses_human_units():
    assert GrowthRewardService.format_reward(ReferralRewardORM.TYPE_EXTRA_TRIAL, 2) == "2 extra trials"
    assert "GB" in GrowthRewardService.format_reward(ReferralRewardORM.TYPE_BONUS_DATA, 1024 ** 3)
    assert GrowthRewardService.format_reward(ReferralRewardORM.TYPE_BONUS_DURATION, 86400) == "1 day(s) bonus duration"


def test_phase66_public_reward_projection_does_not_expose_internal_fields():
    row = SimpleNamespace(
        public_reward_id="RWD-PUBLIC",
        source_type="mission",
        source_reference="mission:public-reference",
        reward_type=ReferralRewardORM.TYPE_EXTRA_TRIAL,
        reward_value=1,
        status=ReferralRewardORM.STATUS_GRANTED,
        created_at=None,
        granted_at=None,
        policy_snapshot_json={"expiry_seconds": 3600},
        beneficiary_user_id=12345,
        risk_result="safe",
        limit_result="eligible",
        failure_reason=None,
    )
    projected = GrowthRewardService._reward(row)
    assert projected["public_reward_id"] == "RWD-PUBLIC"
    assert projected["source_type"] == "mission"
    assert "beneficiary_user_id" not in projected
    assert "risk_result" not in projected
    assert "limit_result" not in projected
    assert "failure_reason" not in projected


@pytest.mark.asyncio
async def test_phase66_admin_overview_denies_non_admin():
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, model, identifier):
            return SimpleNamespace(is_active=True, role="customer")

        async def execute(self, query):
            raise AssertionError("queries must not run after authorization failure")

    class FakeDB:
        def session(self):
            return FakeSession()

    result = await GrowthRewardService(FakeDB()).admin_overview(99)
    assert not result.is_success
    assert result.error.code == "permission_denied"


@pytest.mark.asyncio
async def test_phase66_entitlement_consumption_is_idempotent(tmp_path):
    from database.connection import DatabaseManager
    from database.models.free_trial_entitlement import FreeTrialEntitlementORM
    from database.models.user import UserORM

    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'phase66_entitlement.db'}")
    await db.init()
    async with db.session() as session:
        user = UserORM(telegram_id=660001, full_name="Phase 6.6 Test", role="customer", language="en", status="active", is_active=True, is_verified=False)
        session.add(user)
        await session.flush()
        entitlement = FreeTrialEntitlementORM(user_id=user.id, source="mission_reward", remaining_uses=2, status="active")
        session.add(entitlement)
        await session.flush()
        user_id, entitlement_id = user.id, entitlement.id

    service = GrowthRewardService(db)
    first = await service.consume_entitlement(user_id=user_id, entitlement_id=entitlement_id, idempotency_key="phase66:consume:1")
    duplicate = await service.consume_entitlement(user_id=user_id, entitlement_id=entitlement_id, idempotency_key="phase66:consume:1")
    assert first.is_success and first.unwrap()["status"] == "redeemed"
    assert first.unwrap()["remaining_uses"] == 1
    assert duplicate.is_success and duplicate.unwrap()["status"] == "already_redeemed"

    await db.close()
