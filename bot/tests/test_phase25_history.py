"""Phase 2.5 customer history security and read-only tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.services.history_service import HistoryService
from app.services.manual_payment_service import ManualPaymentService
from app.services.payment_submission_service import PaymentSubmissionService
from database.connection import DatabaseManager
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.user import UserORM


async def _seed(tmp_path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'history.db'}")
    await db.init()
    async with db.session() as session:
        customer = UserORM(telegram_id=993001, full_name="History Customer", role="customer", language="en", is_active=True, is_verified=True)
        other = UserORM(telegram_id=993002, full_name="Other Customer", role="customer", language="my", is_active=True, is_verified=True)
        session.add_all([customer, other])
        await session.flush()
        order = OrderORM(
            user_id=customer.telegram_id,
            package_id=1,
            public_order_id="ORD-HISTORY-1",
            checkout_token="checkout-history-1",
            status=OrderORM.STATUS_PAID,
            payment_status=OrderORM.PAYMENT_PAID,
            currency="MMK",
            subtotal_amount=Decimal("8000"),
            total_amount=Decimal("8000"),
            amount=Decimal("8000"),
            package_name_snapshot="Snapshot Premium",
            package_type_snapshot="premium",
            data_limit_gb_snapshot=Decimal("20"),
            duration_days_snapshot=30,
            device_limit_snapshot=3,
            payment_method="wallet",
            payment_reference="WAL-HISTORY-1",
        )
        session.add(order)
    await ManualPaymentService(db).set_methods([
        {"method_id": "wavepay", "name": "WavePay", "currency": "MMK", "instructions": "Send exact amount.", "enabled": True}
    ])
    submission = await PaymentSubmissionService(db).submit(
        user_id=993001,
        public_order_id="ORD-HISTORY-1",
        method_id="wavepay",
        transaction_reference="MANUAL-HISTORY-1",
        proof_file_id="proof-history-1",
        proof_file_unique_id="proof-history-unique-1",
        proof_file_type="photo",
    )
    assert submission.is_failure  # paid orders cannot accept a new manual submission
    return db


@pytest.mark.asyncio
async def test_orders_are_owner_scoped_and_use_snapshot_data(tmp_path):
    db = await _seed(tmp_path)
    service = HistoryService(db)
    page = await service.list_orders(993001)
    assert len(page.items) == 1
    assert page.items[0].package_name == "Snapshot Premium"
    assert page.items[0].data_limit_gb == Decimal("20")
    assert await service.get_order(993002, "ORD-HISTORY-1") is None
    await db.close()


@pytest.mark.asyncio
async def test_payment_history_is_read_only_and_does_not_expose_other_users(tmp_path):
    db = await _seed(tmp_path)
    service = HistoryService(db)
    page = await service.list_payments(993001)
    assert len(page.items) == 1
    assert page.items[0].payment_type == "order"
    assert page.items[0].payment_id == "WAL-HISTORY-1"
    other_page = await service.list_payments(993002)
    assert other_page.items == ()
    async with db.session() as session:
        order = (await session.execute(select(OrderORM).where(OrderORM.public_order_id == "ORD-HISTORY-1"))).scalar_one()
        assert order.status == OrderORM.STATUS_PAID
        assert order.vpn_key_id is None
    await db.close()
