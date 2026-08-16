"""Focused Phase 2.2 wallet-payment safety tests.

These tests intentionally exercise the real async SQLAlchemy session and
migration schema rather than only mocking repository calls.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.wallet_payment_service import WalletPaymentService
from database.connection import DatabaseManager
from database.models.order import OrderORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM
from database.models.wallet import WalletORM


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'wallet_payment.db'}"


async def _seed(tmp_path: Path, *, balance: str = "10000.00"):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    async with db.session() as session:
        user = UserORM(
            telegram_id=990001,
            full_name="Wallet Test User",
            role="customer",
            language="en",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        wallet = WalletORM(
            user_id=user.id,
            balance=Decimal(balance),
            currency="MMK",
            is_frozen=False,
        )
        order = OrderORM(
            user_id=user.id,
            package_id=1,
            public_order_id="ORD-TEST-0001",
            checkout_token="checkout-test-0001",
            status=OrderORM.STATUS_WAITING_PAYMENT,
            payment_status=OrderORM.PAYMENT_UNPAID,
            payment_method=None,
            currency="MMK",
            subtotal_amount=Decimal("8000.00"),
            total_amount=Decimal("8000.00"),
            amount=Decimal("8000.00"),
            package_name_snapshot="Premium",
        )
        session.add_all([wallet, order])
        await session.flush()
        user_id = user.id
    return db, user_id


async def _snapshot(db: DatabaseManager, user_id: int):
    async with db.session() as session:
        wallet = await session.get(WalletORM, user_id)
        # user_id is not wallet id, so select by owner for the assertion helper.
        from sqlalchemy import select
        wallet = (await session.execute(select(WalletORM).where(WalletORM.user_id == user_id))).scalar_one()
        order = (
            await session.execute(
                select(OrderORM)
                .where(OrderORM.user_id == user_id)
                .order_by(OrderORM.id)
                .limit(1)
            )
        ).scalar_one()
        transactions = (await session.execute(select(TransactionORM))).scalars().all()
        return wallet, order, list(transactions)


@pytest.mark.asyncio
async def test_preview_is_read_only(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = WalletPaymentService(db)

    preview = await service.preview(user_id=user_id, public_order_id="ORD-TEST-0001")

    assert preview.is_success
    assert preview.unwrap().balance_after == Decimal("2000.00")
    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("10000.00")
    assert order.payment_status == OrderORM.PAYMENT_UNPAID
    assert transactions == []
    await db.close()


@pytest.mark.asyncio
async def test_wrong_owner_cannot_preview_or_pay(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = WalletPaymentService(db)

    preview = await service.preview(user_id=user_id + 999, public_order_id="ORD-TEST-0001")
    payment = await service.pay(user_id=user_id + 999, public_order_id="ORD-TEST-0001")

    assert preview.is_failure and preview.error.code == "order_not_found"
    assert payment.is_failure and payment.error.code == "order_not_found"
    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("10000.00")
    assert order.payment_status == OrderORM.PAYMENT_UNPAID
    assert transactions == []
    await db.close()


@pytest.mark.asyncio
async def test_atomic_wallet_payment_debits_ledger_and_order_together(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = WalletPaymentService(db)

    result = await service.pay(user_id=user_id, public_order_id="ORD-TEST-0001")

    assert result.is_success
    receipt = result.unwrap()
    assert receipt.amount == Decimal("8000.00")
    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("2000.00")
    assert order.payment_status == OrderORM.PAYMENT_PAID
    assert order.status == OrderORM.STATUS_PAID
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("-8000.00")
    assert transactions[0].order_id == order.id
    await db.close()


@pytest.mark.asyncio
async def test_repeated_same_payment_is_idempotent(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = WalletPaymentService(db)

    first = await service.pay(user_id=user_id, public_order_id="ORD-TEST-0001")
    second = await service.pay(user_id=user_id, public_order_id="ORD-TEST-0001")

    assert first.is_success and second.is_success
    assert second.unwrap().already_processed is True
    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("2000.00")
    assert order.payment_status == OrderORM.PAYMENT_PAID
    assert len(transactions) == 1
    await db.close()


@pytest.mark.asyncio
async def test_insufficient_balance_is_a_noop(tmp_path):
    db, user_id = await _seed(tmp_path, balance="5000.00")
    service = WalletPaymentService(db)

    result = await service.pay(user_id=user_id, public_order_id="ORD-TEST-0001")

    assert result.is_failure
    assert result.error is not None and result.error.code == "insufficient_balance"
    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("5000.00")
    assert order.payment_status == OrderORM.PAYMENT_UNPAID
    assert transactions == []
    await db.close()


@pytest.mark.asyncio
async def test_failure_after_debit_rolls_back_everything(tmp_path):
    db, user_id = await _seed(tmp_path)

    class FailingWalletPaymentService(WalletPaymentService):
        async def _after_debit(self, order, wallet):
            raise RuntimeError("injected failure")

    service = FailingWalletPaymentService(db)
    with pytest.raises(RuntimeError, match="injected failure"):
        await service.pay(user_id=user_id, public_order_id="ORD-TEST-0001")

    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("10000.00")
    assert order.payment_status == OrderORM.PAYMENT_UNPAID
    assert order.status == OrderORM.STATUS_WAITING_PAYMENT
    assert transactions == []
    await db.close()


@pytest.mark.asyncio
async def test_two_different_orders_cannot_double_spend(tmp_path):
    db, user_id = await _seed(tmp_path)
    async with db.session() as session:
        second_order = OrderORM(
            user_id=user_id,
            package_id=2,
            public_order_id="ORD-TEST-0002",
            checkout_token="checkout-test-0002",
            status=OrderORM.STATUS_WAITING_PAYMENT,
            payment_status=OrderORM.PAYMENT_UNPAID,
            currency="MMK",
            subtotal_amount=Decimal("8000.00"),
            total_amount=Decimal("8000.00"),
            amount=Decimal("8000.00"),
            package_name_snapshot="Premium 2",
        )
        session.add(second_order)

    service = WalletPaymentService(db)
    results = await asyncio.gather(
        service.pay(user_id=user_id, public_order_id="ORD-TEST-0001", idempotency_key="order-a"),
        service.pay(user_id=user_id, public_order_id="ORD-TEST-0002", idempotency_key="order-b"),
    )

    successful = [result for result in results if result.is_success]
    assert len(successful) == 1
    wallet, _, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) >= Decimal("0")
    assert Decimal(str(wallet.balance)) == Decimal("2000.00")
    assert len(transactions) == 1
    await db.close()


@pytest.mark.asyncio
async def test_two_different_requests_cannot_double_spend(tmp_path):
    db, user_id = await _seed(tmp_path)
    service = WalletPaymentService(db)

    results = await asyncio.gather(
        service.pay(
            user_id=user_id,
            public_order_id="ORD-TEST-0001",
            idempotency_key="wallet-request-a",
        ),
        service.pay(
            user_id=user_id,
            public_order_id="ORD-TEST-0001",
            idempotency_key="wallet-request-b",
        ),
    )

    successful = [result for result in results if result.is_success]
    assert len(successful) == 1
    wallet, order, transactions = await _snapshot(db, user_id)
    assert Decimal(str(wallet.balance)) == Decimal("2000.00")
    assert order.payment_status == OrderORM.PAYMENT_PAID
    assert len(transactions) == 1
    await db.close()
