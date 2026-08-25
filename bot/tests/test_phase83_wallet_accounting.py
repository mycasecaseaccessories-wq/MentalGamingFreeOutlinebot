from __future__ import annotations

from decimal import Decimal
from pathlib import Path  # noqa: TC003

import pytest
from sqlalchemy import select

from app.services.wallet_accounting_service import WalletAccountingService
from database.connection import DatabaseManager
from database.models.transaction import TransactionORM
from database.models.user import UserORM
from database.models.wallet import WalletORM


async def _db(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(f"sqlite+aiosqlite:///{tmp_path / 'accounting.db'}")
    await db.init()
    async with db.session() as session:
        user = UserORM(
            telegram_id=830001,
            full_name="Accounting User",
            role="customer",
            language="en",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        session.add(WalletORM(user_id=user.id, balance=Decimal("100.00"), currency="MMK"))
    return db, user.id


@pytest.mark.asyncio
async def test_credit_is_idempotent_and_durable(tmp_path: Path):
    db, user_id = await _db(tmp_path)
    service = WalletAccountingService(db)
    first = await service.credit(
        user_id=user_id,
        amount="25.00",
        currency="mmk",
        source_type="promo",
        source_reference="promo-1",
        idempotency_key="promo:promo-1",
    )
    second = await service.credit(
        user_id=user_id,
        amount="25.00",
        currency="MMK",
        source_type="promo",
        source_reference="promo-1",
        idempotency_key="promo:promo-1",
    )
    assert first.is_success and second.is_success
    assert second.unwrap().idempotent is True
    async with db.session() as session:
        wallet = (await session.execute(select(WalletORM))).scalar_one()
        ledger = list((await session.execute(select(TransactionORM))).scalars())
    assert Decimal(str(wallet.balance)) == Decimal("125.00")
    assert len(ledger) == 1
    await db.close()


@pytest.mark.asyncio
async def test_debit_rejects_invalid_or_insufficient_values(tmp_path: Path):
    db, user_id = await _db(tmp_path)
    service = WalletAccountingService(db)
    invalid = await service.debit(
        user_id=user_id,
        amount="NaN",
        currency="MMK",
        source_type="purchase",
        source_reference="order-1",
        idempotency_key="purchase:order-1",
    )
    insufficient = await service.debit(
        user_id=user_id,
        amount="101.00",
        currency="MMK",
        source_type="purchase",
        source_reference="order-2",
        idempotency_key="purchase:order-2",
    )
    assert invalid.is_failure and invalid.error.code == "invalid_amount"
    assert insufficient.is_failure and insufficient.error.code == "insufficient_balance"
    await db.close()


@pytest.mark.asyncio
async def test_concurrent_debits_cannot_double_spend(tmp_path: Path):
    db, user_id = await _db(tmp_path)
    service = WalletAccountingService(db)
    results = await __import__("asyncio").gather(
        service.debit(
            user_id=user_id,
            amount="80.00",
            currency="MMK",
            source_type="purchase",
            source_reference="concurrent-1",
            idempotency_key="purchase:concurrent-1",
        ),
        service.debit(
            user_id=user_id,
            amount="80.00",
            currency="MMK",
            source_type="purchase",
            source_reference="concurrent-2",
            idempotency_key="purchase:concurrent-2",
        ),
    )
    assert sum(result.is_success for result in results) == 1
    async with db.session() as session:
        wallet = (await session.execute(select(WalletORM))).scalar_one()
    assert Decimal(str(wallet.balance)) == Decimal("20.00")
    await db.close()


@pytest.mark.asyncio
async def test_debit_cannot_cross_currency_or_frozen_wallet(tmp_path: Path):
    db, user_id = await _db(tmp_path)
    service = WalletAccountingService(db)
    mismatch = await service.debit(
        user_id=user_id,
        amount="1.00",
        currency="USD",
        source_type="purchase",
        source_reference="order-3",
        idempotency_key="purchase:order-3",
    )
    async with db.session() as session:
        wallet = (await session.execute(select(WalletORM))).scalar_one()
        wallet.is_frozen = True
    frozen = await service.debit(
        user_id=user_id,
        amount="1.00",
        currency="MMK",
        source_type="purchase",
        source_reference="order-4",
        idempotency_key="purchase:order-4",
    )
    assert mismatch.is_failure and mismatch.error.code == "currency_mismatch"
    assert frozen.is_failure and frozen.error.code == "wallet_frozen"
    await db.close()
