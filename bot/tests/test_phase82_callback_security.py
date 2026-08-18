from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.services.callback_security_service import CallbackSecurityService
from database.connection import DatabaseManager
from database.models.callback_security import CallbackActionORM, CallbackRateLimitORM


def _url(tmp_path):
    return f"sqlite+aiosqlite:///{tmp_path / 'phase82.db'}"


@pytest.fixture
async def callback_security(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    service = CallbackSecurityService(db)
    yield service
    await db.close()
    DatabaseManager._instance = None


@pytest.mark.asyncio
async def test_callback_reference_is_bound_to_actor_chat_resource_and_single_use(callback_security):
    issued = await callback_security.issue(
        action_type="vpn.disable",
        actor_user_id=10,
        actor_telegram_id=1010,
        chat_id=555,
        chat_type="private",
        resource_type="vpn_key",
        resource_public_id="VPN-public-1",
        state_version="active:v1",
    )
    assert issued.is_success
    reference = issued.unwrap()

    copied = await callback_security.consume(
        callback_data=reference.data,
        action_type="vpn.disable",
        actor_user_id=11,
        actor_telegram_id=1111,
        chat_id=555,
        chat_type="private",
        expected_resource_type="vpn_key",
        expected_resource_public_id="VPN-public-1",
        expected_state_version="active:v1",
    )
    assert copied.error is not None
    assert copied.error.code == "callback_not_owned"

    wrong_resource = await callback_security.consume(
        callback_data=reference.data,
        action_type="vpn.disable",
        actor_user_id=10,
        actor_telegram_id=1010,
        chat_id=555,
        chat_type="private",
        expected_resource_type="vpn_key",
        expected_resource_public_id="VPN-public-2",
        expected_state_version="active:v1",
    )
    assert wrong_resource.error is not None
    assert wrong_resource.error.code == "callback_resource_mismatch"

    consumed = await callback_security.consume(
        callback_data=reference.data,
        action_type="vpn.disable",
        actor_user_id=10,
        actor_telegram_id=1010,
        chat_id=555,
        chat_type="private",
        expected_resource_type="vpn_key",
        expected_resource_public_id="VPN-public-1",
        expected_state_version="active:v1",
    )
    assert consumed.is_success

    replay = await callback_security.consume(
        callback_data=reference.data,
        action_type="vpn.disable",
        actor_user_id=10,
        actor_telegram_id=1010,
        chat_id=555,
        chat_type="private",
        expected_resource_type="vpn_key",
        expected_resource_public_id="VPN-public-1",
        expected_state_version="active:v1",
    )
    assert replay.error is not None
    assert replay.error.code == "callback_replayed"


@pytest.mark.asyncio
async def test_callback_rejects_forgery_expiry_stale_and_malformed_data(callback_security):
    forged = await callback_security.consume(
        callback_data="cb2:cba_fake:forged-token-that-is-long-enough",
        action_type="wallet.pay",
        actor_user_id=1,
        actor_telegram_id=1001,
    )
    assert forged.error is not None
    assert forged.error.code == "invalid_callback"

    issued = await callback_security.issue(
        action_type="wallet.pay",
        actor_user_id=1,
        actor_telegram_id=1001,
        ttl_seconds=15,
        state_version="pending:v2",
    )
    reference = issued.unwrap()
    async with callback_security.db.session() as session:
        row = (
            await session.execute(
                select(CallbackActionORM).where(CallbackActionORM.public_id == reference.public_id)
            )
        ).scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    expired = await callback_security.consume(
        callback_data=reference.data,
        action_type="wallet.pay",
        actor_user_id=1,
        actor_telegram_id=1001,
    )
    assert expired.error is not None
    assert expired.error.code == "callback_expired"

    stale_issue = await callback_security.issue(
        action_type="order.cancel",
        actor_user_id=1,
        actor_telegram_id=1001,
        state_version="open:v1",
    )
    stale = await callback_security.consume(
        callback_data=stale_issue.unwrap().data,
        action_type="order.cancel",
        actor_user_id=1,
        actor_telegram_id=1001,
        expected_state_version="open:v2",
    )
    assert stale.error is not None
    assert stale.error.code == "callback_stale"


@pytest.mark.asyncio
async def test_rate_limit_is_durable_and_scoped(callback_security):
    first = await callback_security.check_rate_limit(
        actor_user_id=7, action_type="mission.claim", chat_id=70, limit=2, window_seconds=60
    )
    second = await callback_security.check_rate_limit(
        actor_user_id=7, action_type="mission.claim", chat_id=70, limit=2, window_seconds=60
    )
    third = await callback_security.check_rate_limit(
        actor_user_id=7, action_type="mission.claim", chat_id=70, limit=2, window_seconds=60
    )
    other_action = await callback_security.check_rate_limit(
        actor_user_id=7, action_type="menu.open", chat_id=70, limit=2, window_seconds=60
    )
    assert first.unwrap() is True
    assert second.unwrap() is True
    assert third.unwrap() is False
    assert other_action.unwrap() is True
    async with callback_security.db.session() as session:
        rows = (await session.execute(select(CallbackRateLimitORM))).scalars().all()
        assert len(rows) == 2
