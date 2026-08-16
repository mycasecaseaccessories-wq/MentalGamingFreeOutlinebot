"""Focused Phase 2.4 admin payment review tests."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.manual_payment_service import ManualPaymentService
from app.services.payment_review_service import PaymentReviewService
from app.services.payment_submission_service import PaymentSubmissionService
from database.connection import DatabaseManager
from database.models.audit_log import AuditLogORM
from database.models.notification import NotificationORM
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.user import UserORM


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'payment_review.db'}"


async def _seed(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    async with db.session() as session:
        admin = UserORM(telegram_id=992001, full_name="Review Admin", role="admin", language="en", is_active=True, is_verified=True)
        customer = UserORM(telegram_id=992002, full_name="Review Customer", role="customer", language="my", is_active=True, is_verified=True)
        session.add_all([admin, customer])
        await session.flush()
        order = OrderORM(
            user_id=customer.telegram_id,
            package_id=1,
            public_order_id="ORD-REVIEW-0001",
            checkout_token="checkout-review-0001",
            status=OrderORM.STATUS_WAITING_PAYMENT,
            payment_status=OrderORM.PAYMENT_UNPAID,
            currency="MMK",
            subtotal_amount=Decimal("8000.00"),
            total_amount=Decimal("8000.00"),
            amount=Decimal("8000.00"),
            package_name_snapshot="Premium",
        )
        session.add(order)
        await session.flush()
        admin_id = admin.telegram_id
        customer_id = customer.telegram_id

    await ManualPaymentService(db).set_methods([
        {"method_id": "wavepay", "name": "WavePay", "currency": "MMK", "instructions": "Send exact amount.", "enabled": True}
    ])
    submission = await PaymentSubmissionService(db).submit(
        user_id=customer_id,
        public_order_id="ORD-REVIEW-0001",
        method_id="wavepay",
        transaction_reference="TX-REVIEW-1",
        proof_file_id="proof-file-1",
        proof_file_unique_id="proof-unique-1",
        proof_file_type="photo",
    )
    assert submission.is_success
    return db, admin_id, customer_id, submission.unwrap().public_payment_id


async def _rows(db):
    from sqlalchemy import select

    async with db.session() as session:
        order = (await session.execute(select(OrderORM).where(OrderORM.public_order_id == "ORD-REVIEW-0001"))).scalar_one()
        submission = (await session.execute(select(PaymentSubmissionORM))).scalar_one()
        audits = list((await session.execute(select(AuditLogORM))).scalars().all())
        notifications = list((await session.execute(select(NotificationORM))).scalars().all())
        return order, submission, audits, notifications


@pytest.mark.asyncio
async def test_non_admin_cannot_decide_payment(tmp_path):
    db, _, customer_id, payment_id = await _seed(tmp_path)
    result = await PaymentReviewService(db).approve(actor_telegram_id=customer_id, public_payment_id=payment_id)
    assert result.is_failure and result.error.code == "unauthorized"
    _, submission, audits, notifications = await _rows(db)
    assert submission.status == PaymentSubmissionORM.STATUS_PENDING_REVIEW
    assert audits == []
    assert notifications == []
    await db.close()


@pytest.mark.asyncio
async def test_approval_is_atomic_paid_boundary_and_never_provisions(tmp_path):
    db, admin_id, _, payment_id = await _seed(tmp_path)
    result = await PaymentReviewService(db).approve(actor_telegram_id=admin_id, public_payment_id=payment_id, request_id="req-approve-1")

    assert result.is_success
    decision = result.unwrap()
    assert decision.decision == PaymentSubmissionORM.STATUS_APPROVED
    order, submission, audits, notifications = await _rows(db)
    assert submission.status == PaymentSubmissionORM.STATUS_APPROVED
    assert submission.reviewed_by == admin_id
    assert submission.reviewed_at is not None and submission.approved_at is not None
    assert order.status == OrderORM.STATUS_PAID
    assert order.payment_status == OrderORM.PAYMENT_PAID
    assert order.paid_at is not None
    assert order.vpn_key_id is None
    assert order.wallet_transaction_id is None
    assert len(audits) == 1 and audits[0].action == "manual_payment.approved"
    assert len(notifications) >= 1
    assert any(n.type == "manual_payment_approved" and n.user_id == 992002 for n in notifications)
    await db.close()


@pytest.mark.asyncio
async def test_repeated_approval_returns_terminal_result_without_duplicate_side_effects(tmp_path):
    db, admin_id, _, payment_id = await _seed(tmp_path)
    service = PaymentReviewService(db)
    first = await service.approve(actor_telegram_id=admin_id, public_payment_id=payment_id)
    second = await service.approve(actor_telegram_id=admin_id, public_payment_id=payment_id)

    assert first.is_success and second.is_success
    assert second.unwrap().already_decided is True
    _, submission, audits, notifications = await _rows(db)
    assert submission.status == PaymentSubmissionORM.STATUS_APPROVED
    assert len(audits) == 1
    assert len([n for n in notifications if n.type == "manual_payment_approved"]) == 1
    await db.close()


@pytest.mark.asyncio
async def test_concurrent_admin_approvals_have_one_terminal_decision(tmp_path):
    db, admin_id, _, payment_id = await _seed(tmp_path)
    service = PaymentReviewService(db)
    results = await asyncio.gather(
        service.approve(actor_telegram_id=admin_id, public_payment_id=payment_id, request_id="req-a"),
        service.approve(actor_telegram_id=admin_id, public_payment_id=payment_id, request_id="req-b"),
        return_exceptions=True,
    )
    order, submission, audits, notifications = await _rows(db)
    assert submission.status == PaymentSubmissionORM.STATUS_APPROVED
    assert order.status == OrderORM.STATUS_PAID
    assert len(audits) == 1
    assert len([n for n in notifications if n.type == "manual_payment_approved"]) == 1
    assert sum(1 for result in results if getattr(result, "is_success", False) and not result.unwrap().already_decided) == 1
    await db.close()


@pytest.mark.asyncio
async def test_concurrent_approve_reject_cannot_split_terminal_state(tmp_path):
    db, admin_id, _, payment_id = await _seed(tmp_path)
    service = PaymentReviewService(db)
    results = await asyncio.gather(
        service.approve(actor_telegram_id=admin_id, public_payment_id=payment_id, request_id="req-approve"),
        service.reject(actor_telegram_id=admin_id, public_payment_id=payment_id, reason="Payment Not Received", request_id="req-reject"),
        return_exceptions=True,
    )
    order, submission, audits, notifications = await _rows(db)
    assert submission.status in {PaymentSubmissionORM.STATUS_APPROVED, PaymentSubmissionORM.STATUS_REJECTED}
    if submission.status == PaymentSubmissionORM.STATUS_APPROVED:
        assert order.status == OrderORM.STATUS_PAID
    else:
        assert order.status == OrderORM.STATUS_WAITING_PAYMENT
        assert order.payment_status == OrderORM.PAYMENT_UNPAID
    assert len(audits) == 1
    assert len([n for n in notifications if n.type in {"manual_payment_approved", "manual_payment_rejected"}]) == 1
    terminal_successes = [result for result in results if getattr(result, "is_success", False) and not result.unwrap().already_decided]
    assert len(terminal_successes) == 1
    await db.close()


@pytest.mark.asyncio
async def test_rejection_returns_order_to_unpaid_waiting_payment_and_preserves_history(tmp_path):
    db, admin_id, _, payment_id = await _seed(tmp_path)
    result = await PaymentReviewService(db).reject(
        actor_telegram_id=admin_id,
        public_payment_id=payment_id,
        reason="Payment Not Received",
    )

    assert result.is_success
    order, submission, audits, notifications = await _rows(db)
    assert submission.status == PaymentSubmissionORM.STATUS_REJECTED
    assert submission.rejected_at is not None
    assert submission.reviewed_by == admin_id
    assert submission.rejection_reason == "Payment Not Received"
    assert order.status == OrderORM.STATUS_WAITING_PAYMENT
    assert order.payment_status == OrderORM.PAYMENT_UNPAID
    assert order.vpn_key_id is None
    assert len(audits) == 1 and audits[0].action == "manual_payment.rejected"
    assert any(n.type == "manual_payment_rejected" for n in notifications)
    await db.close()
