"""Phase 2.3 manual payment submission boundary tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.services.manual_payment_service import ManualPaymentService
from app.services.payment_submission_service import PaymentSubmissionService
from database.connection import DatabaseManager
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.user import UserORM


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'manual_payment.db'}"


async def _seed(tmp_path: Path, *, expired: bool = False):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    async with db.session() as session:
        user = UserORM(
            telegram_id=991001,
            full_name="Manual Payment Test User",
            role="customer",
            language="en",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        order = OrderORM(
            user_id=user.id,
            package_id=1,
            public_order_id="ORD-MANUAL-0001",
            checkout_token="checkout-manual-0001",
            status=OrderORM.STATUS_WAITING_PAYMENT,
            payment_status=OrderORM.PAYMENT_UNPAID,
            payment_method=None,
            currency="MMK",
            subtotal_amount=Decimal("8000.00"),
            total_amount=Decimal("8000.00"),
            amount=Decimal("8000.00"),
            package_name_snapshot="Premium",
        )
        if expired:
            from datetime import datetime, timedelta, timezone
            order.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(order)
        await session.flush()
        user_id = user.id

    await ManualPaymentService(db).set_methods([
        {
            "method_id": "wavepay",
            "name": "WavePay",
            "currency": "MMK",
            "instructions": "Send the exact amount to the configured account.",
            "account_name": "Mental Outline VPN",
            "account_number": "09990000000",
            "enabled": True,
        }
    ])
    return db, user_id


async def _snapshot(db: DatabaseManager, user_id: int):
    from sqlalchemy import select

    async with db.session() as session:
        order = (
            await session.execute(select(OrderORM).where(OrderORM.user_id == user_id))
        ).scalar_one()
        submissions = (
            await session.execute(select(PaymentSubmissionORM).where(PaymentSubmissionORM.user_id == user_id))
        ).scalars().all()
        return order, list(submissions)


@pytest.mark.asyncio
async def test_proof_submission_stays_pending_review_and_never_paid(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = PaymentSubmissionService(db)

    result = await service.submit(
        user_id=user_id,
        public_order_id="ORD-MANUAL-0001",
        method_id="wavepay",
        transaction_reference="TX-1001",
        proof_file_id="telegram-file-1",
        proof_file_unique_id="telegram-unique-1",
        proof_file_type="photo",
    )

    assert result.is_success
    receipt = result.unwrap()
    assert receipt.status == PaymentSubmissionORM.STATUS_PENDING_REVIEW
    order, submissions = await _snapshot(db, user_id)
    assert order.status == OrderORM.STATUS_AWAITING_APPROVAL
    assert order.payment_status == OrderORM.PAYMENT_UNDER_REVIEW
    assert order.status != OrderORM.STATUS_PAID
    assert len(submissions) == 1
    assert submissions[0].status == PaymentSubmissionORM.STATUS_PENDING_REVIEW
    assert submissions[0].proof_file_id == "telegram-file-1"
    assert submissions[0].proof_file_unique_id == "telegram-unique-1"
    assert submissions[0].proof_file_type == "photo"
    assert submissions[0].metadata_json == {"source": "telegram", "review_required": True}
    await db.close()


@pytest.mark.asyncio
async def test_same_proof_is_idempotent_and_does_not_create_second_submission(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = PaymentSubmissionService(db)
    payload = dict(
        user_id=user_id,
        public_order_id="ORD-MANUAL-0001",
        method_id="wavepay",
        transaction_reference="TX-1002",
        proof_file_id="telegram-file-2",
        proof_file_unique_id="telegram-unique-2",
        proof_file_type="photo",
    )

    first = await service.submit(**payload)
    second = await service.submit(**payload)

    assert first.is_success and second.is_success
    assert second.unwrap().duplicate is True
    _, submissions = await _snapshot(db, user_id)
    assert len(submissions) == 1
    await db.close()


@pytest.mark.asyncio
async def test_already_paid_order_rejects_proof_without_creating_submission(tmp_path):
    db, user_id = await _seed(tmp_path)
    from sqlalchemy import select

    async with db.session() as session:
        order = (await session.execute(select(OrderORM).where(OrderORM.user_id == user_id))).scalar_one()
        order.status = OrderORM.STATUS_PAID
        order.payment_status = OrderORM.PAYMENT_PAID

    result = await PaymentSubmissionService(db).submit(
        user_id=user_id,
        public_order_id="ORD-MANUAL-0001",
        method_id="wavepay",
        transaction_reference="TX-PAID",
        proof_file_id="telegram-file-paid",
    )
    assert result.is_failure and result.error.code == "already_paid"
    _, submissions = await _snapshot(db, user_id)
    assert submissions == []
    await db.close()


@pytest.mark.asyncio
async def test_wrong_owner_and_expired_order_cannot_submit_proof(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = PaymentSubmissionService(db)

    wrong_owner = await service.submit(
        user_id=user_id + 500,
        public_order_id="ORD-MANUAL-0001",
        method_id="wavepay",
        transaction_reference="TX-IDOR",
        proof_file_id="telegram-file-idor",
    )
    assert wrong_owner.is_failure and wrong_owner.error.code == "order_not_found"
    await db.close()

    expired_root = tmp_path / "expired"
    expired_root.mkdir()
    expired_db, expired_user_id = await _seed(expired_root, expired=True)
    expired = await PaymentSubmissionService(expired_db).submit(
        user_id=expired_user_id,
        public_order_id="ORD-MANUAL-0001",
        method_id="wavepay",
        transaction_reference="TX-EXPIRED",
        proof_file_id="telegram-file-expired",
    )
    assert expired.is_failure and expired.error.code == "order_expired"
    await expired_db.close()
