from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from sqlalchemy import select

from app.models.admin_security import AdminPrincipalStatus, AdminRole
from app.services.admin_authorization_service import AdminAuthorizationService
from app.services.admin_wallet_adjustment_service import AdminWalletAdjustmentService
from app.services.manual_payment_account_admin_service import ManualPaymentAccountAdminService
from database.connection import DatabaseManager
from database.models.audit_log import AuditLogORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM
from database.models.wallet import WalletORM


def _url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'phase83_admin_adjustment.db'}"


async def _seed(tmp_path: Path):
    DatabaseManager._instance = None
    db = DatabaseManager.initialise(_url(tmp_path))
    await db.init()
    async with db.session() as session:
        session.add_all(
            [
                UserORM(
                    telegram_id=883101,
                    full_name="Finance Admin",
                    role="admin",
                    language="en",
                    is_active=True,
                    is_verified=True,
                ),
                UserORM(
                    telegram_id=883103,
                    full_name="Finance Delegate",
                    role="admin",
                    language="en",
                    is_active=True,
                    is_verified=True,
                ),
                UserORM(
                    telegram_id=883102,
                    full_name="Wallet Customer",
                    role="customer",
                    language="en",
                    is_active=True,
                    is_verified=True,
                ),
            ]
        )
    authorization = AdminAuthorizationService(db)
    owner = await authorization.ensure_bootstrap_admin(883101, {883101})
    assert owner is not None
    assert (await authorization.resolve_principal(883103)) is not None
    role_changed = await authorization.change_role(883101, 883103, AdminRole.FINANCE.value)
    assert role_changed.is_success
    return db, authorization


async def _challenge(
    authorization: AdminAuthorizationService,
    amount: str = "25.00",
    actor_telegram_id: int = 883101,
):
    payload = {
        "target_user_id": 883102,
        "amount": amount,
        "currency": "MMK",
        "reason": "Support credit",
        "request_id": "admin-adjustment-e2e-1",
    }
    created = await authorization.create_challenge(
        actor_telegram_id,
        action_type="wallet.adjust",
        permission="adjust_wallet",
        target_type="User",
        target_safe_id="883102",
        payload=payload,
        chat_type="private",
    )
    assert created.is_success
    return created.unwrap().public_id


@pytest.mark.asyncio
async def test_admin_adjustment_confirmation_to_ledger_is_atomic(tmp_path: Path):
    db, authorization = await _seed(tmp_path)
    challenge_id = await _challenge(authorization)
    service = AdminWalletAdjustmentService(db, authorization=authorization)
    result = await service.adjust(
        actor_telegram_id=883101,
        target_user_id=883102,
        amount=Decimal("25.00"),
        currency="MMK",
        reason="Support credit",
        request_id="admin-adjustment-e2e-1",
        challenge_id=challenge_id,
        chat_type="private",
    )
    assert result.is_success
    async with db.session() as session:
        wallet = (
            await session.execute(select(WalletORM).where(WalletORM.user_id == 883102))
        ).scalar_one()
        ledger = (
            (
                await session.execute(
                    select(TransactionORM).where(
                        TransactionORM.idempotency_key == "admin_adjustment:admin-adjustment-e2e-1"
                    )
                )
            )
            .scalars()
            .all()
        )
        audits = (await session.execute(select(AuditLogORM))).scalars().all()
    assert wallet.balance == Decimal("25.00")
    assert len(ledger) == 1
    assert any(a.action == "critical_action.executed" for a in audits)
    await db.close()


@pytest.mark.asyncio
async def test_admin_adjustment_confirmation_replay_has_no_second_effect(tmp_path: Path):
    db, authorization = await _seed(tmp_path)
    challenge_id = await _challenge(authorization)
    service = AdminWalletAdjustmentService(db, authorization=authorization)
    first = await service.adjust(
        actor_telegram_id=883101,
        target_user_id=883102,
        amount=Decimal("25.00"),
        currency="MMK",
        reason="Support credit",
        request_id="admin-adjustment-e2e-1",
        challenge_id=challenge_id,
        chat_type="private",
    )
    replay = await service.adjust(
        actor_telegram_id=883101,
        target_user_id=883102,
        amount=Decimal("25.00"),
        currency="MMK",
        reason="Support credit",
        request_id="admin-adjustment-e2e-1",
        challenge_id=challenge_id,
        chat_type="private",
    )
    assert first.is_success
    assert replay.is_failure and replay.error.code == "challenge_used"
    async with db.session() as session:
        wallet = (
            await session.execute(select(WalletORM).where(WalletORM.user_id == 883102))
        ).scalar_one()
        ledger = (
            (
                await session.execute(
                    select(TransactionORM).where(
                        TransactionORM.idempotency_key == "admin_adjustment:admin-adjustment-e2e-1"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert wallet.balance == Decimal("25.00")
    assert len(ledger) == 1
    await db.close()


@pytest.mark.asyncio
async def test_manual_payment_account_update_requires_confirmation_and_is_replay_safe(
    tmp_path: Path,
):
    db, authorization = await _seed(tmp_path)
    methods = [
        {
            "method_id": "wavepay",
            "name": "WavePay",
            "currency": "MMK",
            "instructions": "Send exact amount.",
            "enabled": True,
            "account_name": "Merchant",
            "account_number": "09xxxx",
            "display_order": 1,
        }
    ]
    canonical_methods = [
        {
            "method_id": "wavepay",
            "name": "WavePay",
            "currency": "MMK",
            "instructions": "Send exact amount.",
            "account_name": "Merchant",
            "account_number": "09xxxx",
            "phone_number": None,
            "wallet_address": None,
            "network": None,
            "min_amount": None,
            "max_amount": None,
            "qr_image_url": None,
            "display_order": 1,
            "enabled": True,
        }
    ]
    payload = {"methods": canonical_methods, "request_id": "payment-config-e2e-1"}
    challenge = await authorization.create_challenge(
        883101,
        action_type="payment_account.update",
        permission="manage_payments",
        target_type="manual_payment_config",
        target_safe_id="global",
        payload=payload,
        chat_type="private",
    )
    assert challenge.is_success
    service = ManualPaymentAccountAdminService(db, authorization=authorization)
    first = await service.update_methods(
        actor_telegram_id=883101,
        methods=methods,
        request_id="payment-config-e2e-1",
        challenge_id=challenge.unwrap().public_id,
        chat_type="private",
    )
    replay = await service.update_methods(
        actor_telegram_id=883101,
        methods=methods,
        request_id="payment-config-e2e-1",
        challenge_id=challenge.unwrap().public_id,
        chat_type="private",
    )
    assert first.is_success
    assert replay.is_failure and replay.error.code == "challenge_used"
    configured = await service.manual_payment.get_method("wavepay")
    assert configured is not None and configured.account_number == "09xxxx"
    await db.close()


@pytest.mark.asyncio
async def test_admin_suspension_before_execution_denies_adjustment(tmp_path: Path):
    db, authorization = await _seed(tmp_path)
    challenge_id = await _challenge(authorization, actor_telegram_id=883103)
    changed = await authorization.change_status(
        883101,
        883103,
        AdminPrincipalStatus.SUSPENDED.value,
        reason="temporary suspension",
    )
    assert changed.is_success
    service = AdminWalletAdjustmentService(db, authorization=authorization)
    result = await service.adjust(
        actor_telegram_id=883103,
        target_user_id=883102,
        amount=Decimal("25.00"),
        currency="MMK",
        reason="Support credit",
        request_id="admin-adjustment-e2e-1",
        challenge_id=challenge_id,
        chat_type="private",
    )
    assert result.is_failure
    await db.close()


@pytest.mark.asyncio
async def test_admin_cross_binding_and_invalid_amount_are_denied(tmp_path: Path):
    db, authorization = await _seed(tmp_path)
    challenge_id = await _challenge(authorization)
    service = AdminWalletAdjustmentService(db, authorization=authorization)
    wrong_target = await service.adjust(
        actor_telegram_id=883101,
        target_user_id=999999,
        amount=Decimal("25.00"),
        currency="MMK",
        reason="Support credit",
        request_id="admin-adjustment-e2e-1",
        challenge_id=challenge_id,
        chat_type="private",
    )
    invalid_amount = await service.adjust(
        actor_telegram_id=883101,
        target_user_id=883102,
        amount=Decimal("NaN"),
        currency="MMK",
        reason="Support credit",
        request_id="admin-adjustment-e2e-2",
        challenge_id=None,
        chat_type="private",
    )
    assert wrong_target.is_failure
    assert invalid_amount.is_failure and invalid_amount.error.code == "invalid_amount"
    await db.close()
