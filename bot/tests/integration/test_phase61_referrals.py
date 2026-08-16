from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.services.referral_service import ReferralService
from app.services.referral_token_service import ReferralTokenService, StartPayloadParser
from database.models.referral import ReferralORM
from database.models.user import UserORM


@pytest_asyncio.fixture
async def referral_db(db_manager):
    from database.base import Base

    async with db_manager._engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return db_manager


async def _user(db, telegram_id: int) -> UserORM:
    async with db.session() as session:
        row = UserORM(
            telegram_id=telegram_id,
            full_name=f"User {telegram_id}",
            first_name="User",
            role="customer",
            language="en",
            status="active",
            is_active=True,
            is_verified=False,
        )
        session.add(row)
        await session.flush()
        return row


@pytest.mark.asyncio
async def test_token_is_stable_unique_valid_and_link_uses_runtime_username(referral_db):
    first = await _user(referral_db, 610001)
    second = await _user(referral_db, 610002)
    service = ReferralTokenService(referral_db)

    first_token = (await service.get_or_create_token(first.id)).unwrap()
    repeated = (await service.get_or_create_token(first.id)).unwrap()
    second_token = (await service.get_or_create_token(second.id)).unwrap()

    assert first_token == repeated
    assert first_token != second_token
    assert service.validate_token_format(first_token)
    assert service.build_referral_link("runtime_bot", first_token) == f"https://t.me/runtime_bot?start=ref_{first_token}"


def test_start_payload_parser_is_namespaced_and_safe():
    assert StartPayloadParser.parse(None)["kind"] == "normal"
    assert StartPayloadParser.parse("ref_AB7K2M9X")["kind"] == "referral"
    assert StartPayloadParser.parse("ref_bad-token")["kind"] == "invalid_referral"
    assert StartPayloadParser.parse("campaign_123")["kind"] == "unknown"


@pytest.mark.asyncio
async def test_valid_attribution_is_pending_and_has_no_reward_side_effect(referral_db):
    referrer = await _user(referral_db, 610011)
    referred = await _user(referral_db, 610012)
    tokens = ReferralTokenService(referral_db)
    token = (await tokens.get_or_create_token(referrer.id)).unwrap()
    service = ReferralService(referral_db, token_service=tokens)

    result = await service.attribute_from_start(referred_id=referred.id, is_new_user=True, raw_payload=f"ref_{token}")
    assert result.is_success
    payload = result.unwrap()
    assert payload["attributed"] is True
    assert payload["status"] == ReferralORM.STATUS_PENDING_QUALIFICATION

    async with referral_db.session() as session:
        row = (await session.execute(select(ReferralORM).where(ReferralORM.referred_id == referred.id))).scalar_one()
        assert row.referrer_id == referrer.id
        assert row.referred_id == referred.id
        assert row.commission is None


@pytest.mark.asyncio
async def test_self_referral_invalid_link_existing_user_and_first_attribution_are_safe(referral_db):
    user_a = await _user(referral_db, 610021)
    user_b = await _user(referral_db, 610022)
    user_c = await _user(referral_db, 610023)
    tokens = ReferralTokenService(referral_db)
    token_a = (await tokens.get_or_create_token(user_a.id)).unwrap()
    token_c = (await tokens.get_or_create_token(user_c.id)).unwrap()
    service = ReferralService(referral_db, token_service=tokens)

    self_result = await service.attribute_from_start(referred_id=user_a.id, is_new_user=True, raw_payload=f"ref_{token_a}")
    assert self_result.is_failure
    assert self_result.error.code == "self_referral"

    invalid = await service.attribute_from_start(referred_id=user_b.id, is_new_user=True, raw_payload="ref_UNKNOWN1")
    assert invalid.is_success and invalid.unwrap()["attributed"] is False

    first = await service.attribute_from_start(referred_id=user_b.id, is_new_user=True, raw_payload=f"ref_{token_a}")
    second = await service.attribute_from_start(referred_id=user_b.id, is_new_user=False, raw_payload=f"ref_{token_c}")
    assert first.unwrap()["attributed"] is True
    assert second.unwrap()["reason"] == "existing_user"

    stats = (await service.stats(user_a.id)).unwrap()
    assert stats["total"] == 1


@pytest.mark.asyncio
async def test_concurrent_attribution_creates_at_most_one_primary_relationship(referral_db):
    referrer_a = await _user(referral_db, 610031)
    referrer_b = await _user(referral_db, 610032)
    referred = await _user(referral_db, 610033)
    tokens = ReferralTokenService(referral_db)
    token_a = (await tokens.get_or_create_token(referrer_a.id)).unwrap()
    token_b = (await tokens.get_or_create_token(referrer_b.id)).unwrap()
    service = ReferralService(referral_db, token_service=tokens)

    results = await asyncio.gather(
        service.attribute_from_start(referred_id=referred.id, is_new_user=True, raw_payload=f"ref_{token_a}"),
        service.attribute_from_start(referred_id=referred.id, is_new_user=True, raw_payload=f"ref_{token_b}"),
    )
    assert sum(1 for result in results if result.is_success and result.unwrap().get("attributed")) <= 1

    async with referral_db.session() as session:
        rows = (await session.execute(select(ReferralORM).where(ReferralORM.referred_id == referred.id))).scalars().all()
        assert len(rows) <= 1
