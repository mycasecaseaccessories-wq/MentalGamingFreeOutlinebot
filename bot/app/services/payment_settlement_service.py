"""Authoritative provider settlement boundary for Phase 8.3.

The Telegram layer can request a verification, but it cannot supply the
financial result. A provider adapter must return a verified amount, currency,
status, and provider-scoped reference before this service mutates state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from database.models.audit_log import AuditLogORM
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.repositories.payment_submission_repository import PaymentSubmissionRepository

from .base import BaseService
from .order_service import InvalidOrderStateError, OrderService
from .payment_provider import PaymentProvider, ProviderVerification


@dataclass(frozen=True, slots=True)
class SettlementReceipt:
    public_payment_id: str
    public_order_id: str
    provider: str
    provider_reference: str
    amount: Decimal
    currency: str
    settled_at: datetime
    already_processed: bool = False


class PaymentSettlementService(BaseService):
    """Settle a payment only after independent provider verification."""

    def __init__(self, db: Any = None, *, provider: PaymentProvider) -> None:
        super().__init__(db)
        self.provider = provider

    async def settle(  # noqa: PLR0911, PLR0912
        self,
        *,
        public_payment_id: str,
        provider_payment_id: str,
    ) -> Result[SettlementReceipt]:
        """Verify with the provider, then atomically settle the locked record."""
        try:
            verification = await self.provider.verify_payment(provider_payment_id)
        except Exception:
            return Failure("provider_verification_failed", "Payment could not be verified.")
        if not self._valid_verification(verification):
            return Failure(
                "provider_verification_failed", "Payment verification was not successful."
            )

        now = datetime.now(UTC)
        try:
            async with self.db.session() as session:
                submissions = PaymentSubmissionRepository(session)
                submission = await submissions.get_for_update_by_public_payment_id(
                    public_payment_id
                )
                if submission is None:
                    return Failure("not_found", "Payment submission not found.")

                if submission.status == PaymentSubmissionORM.STATUS_APPROVED:
                    if (
                        submission.provider == verification.provider
                        and submission.provider_reference == verification.provider_reference
                    ):
                        order = await session.get(OrderORM, submission.order_id)
                        if order is not None:
                            return Success(
                                self._receipt(submission, order, verification, now, True)
                            )
                    return Failure("already_settled", "Payment was already settled.")

                order_result = await session.execute(
                    select(OrderORM).where(OrderORM.id == submission.order_id).with_for_update()
                )
                order = order_result.scalar_one_or_none()
                if (
                    order is None
                    or order.id != submission.order_id
                    or order.user_id != submission.user_id
                ):
                    return Failure("invalid_binding", "Payment and order ownership do not match.")
                if order.payment_submission_id not in {None, submission.id}:
                    return Failure("invalid_binding", "Payment is bound to another submission.")
                if (
                    order.total_amount != submission.amount
                    or order.currency.upper() != submission.currency.upper()
                ):
                    return Failure(
                        "amount_or_currency_mismatch", "Payment does not match the order."
                    )
                if verification.amount != Decimal(str(order.total_amount)):
                    return Failure("amount_mismatch", "Provider amount does not match the order.")
                if verification.currency.upper() != order.currency.upper():
                    return Failure(
                        "currency_mismatch", "Provider currency does not match the order."
                    )
                if order.payment_status not in {
                    OrderORM.PAYMENT_UNPAID,
                    OrderORM.PAYMENT_PENDING,
                    OrderORM.PAYMENT_UNDER_REVIEW,
                } or order.status not in {
                    OrderORM.STATUS_PENDING,
                    OrderORM.STATUS_WAITING_PAYMENT,
                    OrderORM.STATUS_AWAITING_APPROVAL,
                }:
                    return Failure("invalid_payment_state", "The order is not awaiting payment.")

                try:
                    OrderService.validate_transition(order.status, OrderORM.STATUS_PAID)
                except InvalidOrderStateError:
                    return Failure("invalid_payment_state", "The order cannot be settled.")

                submission.provider = verification.provider
                submission.provider_reference = verification.provider_reference
                submission.transaction_reference = verification.provider_reference
                submission.status = PaymentSubmissionORM.STATUS_APPROVED
                submission.reviewed_at = now
                submission.approved_at = now
                order.payment_submission_id = submission.id
                order.payment_method = submission.payment_method
                order.payment_reference = verification.provider_reference
                order.payment_ref = verification.provider_reference
                order.payment_status = OrderORM.PAYMENT_PAID
                order.status = OrderORM.STATUS_PAID
                order.paid_at = now
                order.approved_at = now

                session.add(
                    AuditLogORM(
                        actor_id=None,
                        action="payment.provider_settled",
                        entity_type="PaymentSubmission",
                        entity_id=submission.id,
                        old_value=json.dumps(
                            {"status": PaymentSubmissionORM.STATUS_PENDING_REVIEW}
                        ),
                        new_value=json.dumps(
                            {
                                "status": submission.status,
                                "provider": verification.provider,
                                "provider_reference": verification.provider_reference,
                                "amount": str(verification.amount),
                                "currency": verification.currency.upper(),
                            },
                            sort_keys=True,
                        ),
                        note=f"Authoritative provider settlement for {public_payment_id}",
                    )
                )
                await session.flush()
                receipt = self._receipt(submission, order, verification, now, False)
        except IntegrityError:
            return Failure(
                "provider_reference_conflict", "Provider transaction reference is already in use."
            )

        await bus.emit(
            EventType.ORDER_PAID,
            order_id=order.id,
            user_id=order.user_id,
            public_order_id=receipt.public_order_id,
            payment_reference=receipt.provider_reference,
            provider=receipt.provider,
            provider_reference=receipt.provider_reference,
            amount=str(receipt.amount),
            currency=receipt.currency,
        )
        return Success(receipt)

    @staticmethod
    def _valid_verification(value: ProviderVerification) -> bool:
        return (
            isinstance(value, ProviderVerification)
            and value.is_successful
            and bool(value.provider.strip())
            and bool(value.provider_reference.strip())
            and value.amount.is_finite()
            and value.amount > 0
            and bool(value.currency.strip())
        )

    @staticmethod
    def _receipt(
        submission: PaymentSubmissionORM,
        order: OrderORM,
        verification: ProviderVerification,
        settled_at: datetime,
        already_processed: bool,
    ) -> SettlementReceipt:
        return SettlementReceipt(
            public_payment_id=submission.public_payment_id,
            public_order_id=order.public_order_id,
            provider=verification.provider,
            provider_reference=verification.provider_reference,
            amount=verification.amount,
            currency=verification.currency.upper(),
            settled_at=settled_at,
            already_processed=already_processed,
        )
