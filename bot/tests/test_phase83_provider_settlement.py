from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path  # noqa: TC003

import pytest
from sqlalchemy import select

from app.services.manual_payment_service import ManualPaymentService
from app.services.payment_provider import ProviderRefund, ProviderVerification
from app.services.payment_refund_service import PaymentRefundService
from app.services.payment_settlement_service import PaymentSettlementService
from app.services.payment_submission_service import PaymentSubmissionService
from database.connection import DatabaseManager
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM
from database.models.wallet import WalletORM


class FakeProvider:
    provider_name = "fakepay"

    def __init__(
        self,
        verification: ProviderVerification | None = None,
        refund: ProviderRefund | None = None,
        error: Exception | None = None,
    ):
        self.verification = verification
        self.refund = refund
        self.error = error

    async def verify_payment(self, provider_payment_id: str) -> ProviderVerification:
        if self.error is not None:
            raise self.error
        assert provider_payment_id
        assert self.verification is not None
        return self.verification

    async def refund_payment(
        self,
        provider_reference: str,
        *,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> ProviderRefund:
        if self.error is not None:
            raise self.error
        assert self.refund is not None
        return self.refund


async def _seed(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'phase83_provider.db'}")
    await db.init()
    async with db.session() as session:
        customer = UserORM(
            telegram_id=883002,
            full_name="Phase 8.3 Customer",
            role="customer",
            language="en",
            is_active=True,
            is_verified=True,
        )
        session.add(customer)
        await session.flush()
        order = OrderORM(
            user_id=customer.telegram_id,
            package_id=1,
            public_order_id="ORD-P83-0001",
            checkout_token="checkout-p83-0001",
            status=OrderORM.STATUS_WAITING_PAYMENT,
            payment_status=OrderORM.PAYMENT_UNPAID,
            currency="MMK",
            subtotal_amount=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            amount=Decimal("100.00"),
            package_name_snapshot="P83",
        )
        session.add(order)
    await ManualPaymentService(db).set_methods(
        [
            {
                "method_id": "fakepay",
                "name": "FakePay",
                "currency": "MMK",
                "instructions": "test",
                "enabled": True,
            }
        ]
    )
    submission = await PaymentSubmissionService(db).submit(
        user_id=883002,
        public_order_id="ORD-P83-0001",
        method_id="fakepay",
        transaction_reference="client-reference-is-not-authority",
        proof_file_id="proof",
        proof_file_unique_id="proof-unique",
        proof_file_type="photo",
    )
    assert submission.is_success
    return db, submission.unwrap().public_payment_id


def _verification(amount: str = "100.00", currency: str = "MMK", ref: str = "provider-tx-1"):
    return ProviderVerification(
        provider="fakepay",
        provider_reference=ref,
        status="succeeded",
        amount=Decimal(amount),
        currency=currency,
        verified_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_provider_verification_is_authoritative_and_idempotent(tmp_path: Path):
    db, payment_id = await _seed(tmp_path)
    service = PaymentSettlementService(db, provider=FakeProvider(_verification()))

    first = await service.settle(public_payment_id=payment_id, provider_payment_id="provider-id-1")
    second = await service.settle(public_payment_id=payment_id, provider_payment_id="provider-id-1")

    assert first.is_success
    assert second.is_success
    assert second.unwrap().already_processed is True
    async with db.session() as session:
        order = (
            await session.execute(
                select(OrderORM).where(OrderORM.public_order_id == "ORD-P83-0001")
            )
        ).scalar_one()
        submission = (await session.execute(select(PaymentSubmissionORM))).scalar_one()
    assert order.payment_status == OrderORM.PAYMENT_PAID
    assert submission.provider_reference == "provider-tx-1"
    await db.close()


def _refund(ref: str = "refund-tx-1"):
    return ProviderRefund(
        provider="fakepay",
        provider_reference="provider-tx-1",
        refund_reference=ref,
        status="refunded",
        amount=Decimal("100.00"),
        currency="MMK",
        refunded_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_provider_refund_is_durable_and_idempotent(tmp_path: Path):
    db, payment_id = await _seed(tmp_path)
    settled = await PaymentSettlementService(db, provider=FakeProvider(_verification())).settle(
        public_payment_id=payment_id, provider_payment_id="provider-id-refund"
    )
    assert settled.is_success
    first = await PaymentRefundService(db, provider=FakeProvider(refund=_refund())).refund(
        public_order_id="ORD-P83-0001", request_id="refund-request-1"
    )
    second = await PaymentRefundService(db, provider=FakeProvider(refund=_refund())).refund(
        public_order_id="ORD-P83-0001", request_id="refund-request-1"
    )
    assert first.is_success and second.is_success
    assert second.unwrap().already_processed is True
    await db.close()


@pytest.mark.asyncio
async def test_manual_payment_refund_creates_one_compensating_ledger_entry(tmp_path: Path):
    db, payment_id = await _seed(tmp_path)
    settled = await PaymentSettlementService(db, provider=FakeProvider(_verification())).settle(
        public_payment_id=payment_id, provider_payment_id="provider-id-manual-refund"
    )
    assert settled.is_success
    service = PaymentRefundService(db)
    first = await service.refund(
        public_order_id="ORD-P83-0001", request_id="manual-refund-request-1"
    )
    second = await service.refund(
        public_order_id="ORD-P83-0001", request_id="manual-refund-request-1"
    )
    assert first.is_success and second.is_success
    assert second.unwrap().already_processed is True
    async with db.session() as session:
        wallet = (
            await session.execute(select(WalletORM).where(WalletORM.user_id == 883002))
        ).scalar_one()
        refunds = list(
            (
                await session.execute(
                    select(TransactionORM).where(TransactionORM.type == TransactionORM.TYPE_REFUND)
                )
            ).scalars()
        )
        order = (
            await session.execute(
                select(OrderORM).where(OrderORM.public_order_id == "ORD-P83-0001")
            )
        ).scalar_one()
    assert order.status == OrderORM.STATUS_REFUNDED
    assert wallet.balance == Decimal("100.00")
    assert len(refunds) == 1
    await db.close()


@pytest.mark.asyncio
async def test_provider_amount_mismatch_does_not_settle(tmp_path: Path):
    db, payment_id = await _seed(tmp_path)
    result = await PaymentSettlementService(
        db, provider=FakeProvider(_verification("1.00"))
    ).settle(
        public_payment_id=payment_id,
        provider_payment_id="provider-id-2",
    )
    assert result.is_failure and result.error.code == "amount_mismatch"
    await db.close()


@pytest.mark.asyncio
async def test_provider_currency_mismatch_does_not_settle(tmp_path: Path):
    db, payment_id = await _seed(tmp_path)
    result = await PaymentSettlementService(
        db, provider=FakeProvider(_verification(currency="USD"))
    ).settle(
        public_payment_id=payment_id,
        provider_payment_id="provider-id-3",
    )
    assert result.is_failure and result.error.code == "currency_mismatch"
    await db.close()


@pytest.mark.asyncio
async def test_provider_verification_failure_does_not_mutate(tmp_path: Path):
    db, payment_id = await _seed(tmp_path)
    result = await PaymentSettlementService(
        db, provider=FakeProvider(error=RuntimeError("offline"))
    ).settle(
        public_payment_id=payment_id,
        provider_payment_id="provider-id-4",
    )
    assert result.is_failure and result.error.code == "provider_verification_failed"
    async with db.session() as session:
        submission = (await session.execute(select(PaymentSubmissionORM))).scalar_one()
    assert submission.status == PaymentSubmissionORM.STATUS_PENDING_REVIEW
    await db.close()
