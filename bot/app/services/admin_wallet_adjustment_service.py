"""Privileged wallet adjustment workflow for Phase 8.3."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.result import Failure, Result
from app.services.admin_authorization_service import AdminAuthorizationService
from app.services.wallet_accounting_service import AccountingReceipt, WalletAccountingService


class AdminWalletAdjustmentService:
    """Require fresh finance permission and one-time confirmation before mutation."""

    ACTION_TYPE = "wallet.adjust"
    PERMISSION = "adjust_wallet"

    def __init__(self, db: Any, *, authorization: AdminAuthorizationService | None = None) -> None:
        self.db = db
        self.authorization = authorization or AdminAuthorizationService(db)
        self.accounting = WalletAccountingService(db)

    async def adjust(  # noqa: PLR0911
        self,
        *,
        actor_telegram_id: int,
        target_user_id: int,
        amount: Decimal | int | str,
        currency: str,
        reason: str,
        request_id: str,
        challenge_id: str | None,
        chat_type: str | None = None,
    ) -> Result[AccountingReceipt]:
        """Apply a signed adjustment only after challenge payload revalidation."""
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            return Failure("invalid_amount", "Adjustment amount must be a finite non-zero Decimal.")
        if not value.is_finite() or value == 0:
            return Failure("invalid_amount", "Adjustment amount must be a finite non-zero Decimal.")
        if not reason.strip() or len(reason.strip()) > 512 or not request_id.strip():
            return Failure("invalid_request", "Reason and request ID are required.")
        if not challenge_id:
            return Failure("confirmation_required", "A one-time confirmation is required.")

        payload = {
            "target_user_id": target_user_id,
            "amount": str(value),
            "currency": currency.strip().upper(),
            "reason": reason.strip(),
            "request_id": request_id.strip(),
        }
        confirmed = await self.authorization.consume_challenge(
            actor_telegram_id,
            public_id=challenge_id,
            action_type=self.ACTION_TYPE,
            permission=self.PERMISSION,
            target_type="User",
            target_safe_id=str(target_user_id),
            payload=payload,
            chat_type=chat_type,
        )
        if confirmed.is_failure:
            return confirmed

        if value > 0:
            return await self.accounting.credit(
                user_id=target_user_id,
                amount=value,
                currency=currency,
                source_type="admin_adjustment",
                source_reference=request_id,
                idempotency_key=f"admin_adjustment:{request_id}",
                note=reason.strip(),
            )
        return await self.accounting.debit(
            user_id=target_user_id,
            amount=abs(value),
            currency=currency,
            source_type="admin_adjustment",
            source_reference=request_id,
            idempotency_key=f"admin_adjustment:{request_id}",
            transaction_type="adjustment",
            note=reason.strip(),
        )
