"""Provider-authoritative refund/reversal workflow for Phase 8.3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.services.background_job_service import BackgroundJobService
from app.services.wallet_accounting_service import WalletAccountingService
from database.models.audit_log import AuditLogORM
from database.models.background_job import BackgroundJobORM
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.transaction import TransactionORM
from database.repositories.order_repository import OrderRepository

from .base import BaseService
from .payment_provider import PaymentProvider, ProviderRefund


@dataclass(frozen=True, slots=True)
class RefundReceipt:
    public_order_id: str
    provider: str
    original_reference: str
    refund_reference: str
    amount: Decimal
    currency: str
    refunded_at: datetime
    already_processed: bool = False


class PaymentRefundService(BaseService):
    """Reverse a provider settlement exactly once at the order boundary."""

    def __init__(self, db: Any = None, *, provider: PaymentProvider | None = None) -> None:
        super().__init__(db)
        self.provider = provider

    async def reconcile_job(self, payload: dict[str, Any]) -> Result[RefundReceipt]:
        """Retry a persisted refund intent using the same idempotency key."""
        public_order_id = str(payload.get("public_order_id", ""))
        request_id = str(payload.get("request_id", ""))
        return await self.refund(public_order_id=public_order_id, request_id=request_id)

    async def refund(  # noqa: PLR0911
        self, *, public_order_id: str, request_id: str
    ) -> Result[RefundReceipt]:
        if not public_order_id.strip() or not request_id.strip():
            return Failure("invalid_request", "Order ID and refund request ID are required.")
        async with self.db.session() as session:
            order = await OrderRepository(session).get_for_update_by_public_order_id(
                public_order_id
            )
            if order is None:
                return Failure("not_found", "Order not found.")
            metadata = dict(order.metadata_json or {})
            prior = metadata.get("refund")
            if order.status == OrderORM.STATUS_REFUNDED and isinstance(prior, dict):
                return Success(
                    RefundReceipt(
                        public_order_id=public_order_id,
                        provider=str(prior["provider"]),
                        original_reference=str(prior["original_reference"]),
                        refund_reference=str(prior["refund_reference"]),
                        amount=Decimal(str(prior["amount"])),
                        currency=str(prior["currency"]),
                        refunded_at=datetime.fromisoformat(str(prior["refunded_at"])),
                        already_processed=True,
                    )
                )
            if (
                order.status != OrderORM.STATUS_PAID
                or order.payment_status != OrderORM.PAYMENT_PAID
            ):
                return Failure("invalid_payment_state", "Only paid orders can be refunded.")
            submission = None
            if order.payment_submission_id is not None:
                submission = await session.get(PaymentSubmissionORM, order.payment_submission_id)
            amount = Decimal(str(order.total_amount))
            currency = order.currency.upper()
            provider_name = (submission.provider if submission else None) or "manual"
            original_reference = (
                (submission.provider_reference if submission else None)
                or (submission.transaction_reference if submission else None)
                or public_order_id
            )

        await BackgroundJobService(self.db).enqueue(
            job_type=BackgroundJobORM.JOB_PAYMENT_REFUND_RECONCILIATION,
            logical_key=f"refund:{request_id}",
            payload_safe={
                "public_order_id": public_order_id,
                "request_id": request_id,
                "provider": provider_name,
                "provider_reference": original_reference,
                "amount": str(amount),
                "currency": currency,
            },
        )
        if self.provider is None or provider_name == "manual":
            return await self._commit_manual_refund(
                public_order_id=public_order_id,
                request_id=request_id,
                amount=amount,
                currency=currency,
                original_reference=original_reference,
            )
        if submission is None or not submission.provider:
            return Failure(
                "provider_reference_missing",
                "A provider refund requires a provider record.",
            )
        try:
            provider_refund = await self.provider.refund_payment(
                original_reference,
                amount=amount,
                currency=currency,
                idempotency_key=f"refund:{request_id}",
            )
        except Exception:
            return Failure("provider_refund_failed", "Provider refund could not be completed.")
        if not self._valid_refund(
            provider_refund, provider_name, original_reference, amount, currency
        ):
            return Failure(
                "provider_refund_failed", "Provider did not confirm the requested refund."
            )

        async with self.db.session() as session:
            order = await OrderRepository(session).get_for_update_by_public_order_id(
                public_order_id
            )
            if order is None:
                return Failure("not_found", "Order not found.")
            metadata = dict(order.metadata_json or {})
            if order.status == OrderORM.STATUS_REFUNDED and isinstance(
                metadata.get("refund"), dict
            ):
                prior = metadata["refund"]
                return Success(self._receipt_from_dict(public_order_id, prior, True))
            if (
                order.status != OrderORM.STATUS_PAID
                or order.payment_status != OrderORM.PAYMENT_PAID
            ):
                return Failure("invalid_payment_state", "Order changed before refund commit.")
            record = {
                "request_id": request_id,
                "provider": provider_refund.provider,
                "original_reference": provider_refund.provider_reference,
                "refund_reference": provider_refund.refund_reference,
                "amount": str(provider_refund.amount),
                "currency": provider_refund.currency.upper(),
                "refunded_at": provider_refund.refunded_at.isoformat(),
            }
            metadata["refund"] = record
            order.metadata_json = metadata
            order.status = OrderORM.STATUS_REFUNDED
            order.payment_status = OrderORM.PAYMENT_REFUNDED
            order.payment_reference = provider_refund.refund_reference
            order.payment_ref = provider_refund.refund_reference
            await session.flush()
            session.add(
                AuditLogORM(
                    actor_id=None,
                    action="order.refunded",
                    entity_type="Order",
                    entity_id=order.id,
                    old_value=json.dumps(
                        {"status": OrderORM.STATUS_PAID, "payment_status": OrderORM.PAYMENT_PAID}
                    ),
                    new_value=json.dumps(record, sort_keys=True),
                    note=f"Provider refund committed for {public_order_id}",
                )
            )
            receipt = RefundReceipt(
                public_order_id=public_order_id,
                provider=provider_refund.provider,
                original_reference=provider_refund.provider_reference,
                refund_reference=provider_refund.refund_reference,
                amount=provider_refund.amount,
                currency=provider_refund.currency.upper(),
                refunded_at=provider_refund.refunded_at,
            )
        await bus.emit(
            EventType.ORDER_REFUNDED,
            order_id=order.id,
            public_order_id=public_order_id,
            refund_reference=receipt.refund_reference,
        )
        return Success(receipt)

    async def _commit_manual_refund(
        self,
        *,
        public_order_id: str,
        request_id: str,
        amount: Decimal,
        currency: str,
        original_reference: str,
    ) -> Result[RefundReceipt]:
        async with self.db.session() as session:
            order = await OrderRepository(session).get_for_update_by_public_order_id(
                public_order_id
            )
            if order is None:
                return Failure("not_found", "Order not found.")
            metadata = dict(order.metadata_json or {})
            prior = metadata.get("refund")
            if order.status == OrderORM.STATUS_REFUNDED and isinstance(prior, dict):
                return Success(self._receipt_from_dict(public_order_id, prior, True))
            if (
                order.status != OrderORM.STATUS_PAID
                or order.payment_status != OrderORM.PAYMENT_PAID
            ):
                return Failure("invalid_payment_state", "Only paid orders can be refunded.")
            accounting = WalletAccountingService(self.db)
            credited = await accounting.credit_in_session(
                session,
                user_id=order.user_id,
                amount=amount,
                currency=currency,
                source_type="manual_refund",
                source_reference=request_id,
                idempotency_key=f"refund:{request_id}",
                transaction_type=TransactionORM.TYPE_REFUND,
                note=f"Manual refund for {public_order_id}",
            )
            if credited.is_failure:
                return credited
            now = datetime.now().astimezone()
            refund_reference = f"manual-refund:{request_id}"
            record = {
                "request_id": request_id,
                "provider": "manual",
                "original_reference": original_reference,
                "refund_reference": refund_reference,
                "amount": str(amount),
                "currency": currency,
                "refunded_at": now.isoformat(),
                "ledger_transaction_id": credited.unwrap().transaction_id,
            }
            metadata["refund"] = record
            order.metadata_json = metadata
            order.status = OrderORM.STATUS_REFUNDED
            order.payment_status = OrderORM.PAYMENT_REFUNDED
            order.payment_reference = refund_reference
            order.payment_ref = refund_reference
            session.add(
                AuditLogORM(
                    actor_id=None,
                    action="order.refunded",
                    entity_type="Order",
                    entity_id=order.id,
                    old_value=json.dumps(
                        {"status": OrderORM.STATUS_PAID, "payment_status": OrderORM.PAYMENT_PAID}
                    ),
                    new_value=json.dumps(record, sort_keys=True),
                    note=f"Manual refund compensating ledger committed for {public_order_id}",
                )
            )
            await session.flush()
            receipt = RefundReceipt(
                public_order_id=public_order_id,
                provider="manual",
                original_reference=original_reference,
                refund_reference=refund_reference,
                amount=amount,
                currency=currency,
                refunded_at=now,
            )
        await bus.emit(
            EventType.ORDER_REFUNDED,
            order_id=order.id,
            public_order_id=public_order_id,
            refund_reference=receipt.refund_reference,
        )
        return Success(receipt)

    @staticmethod
    def _valid_refund(
        value: ProviderRefund,
        expected_provider: str,
        expected_original_reference: str,
        expected_amount: Decimal,
        expected_currency: str,
    ) -> bool:
        return bool(
            isinstance(value, ProviderRefund)
            and value.is_successful
            and value.provider == expected_provider
            and value.provider_reference == expected_original_reference
            and value.refund_reference.strip()
            and value.amount == expected_amount
            and value.currency.upper() == expected_currency
        )

    @staticmethod
    def _receipt_from_dict(
        public_order_id: str, record: dict, already_processed: bool
    ) -> RefundReceipt:
        return RefundReceipt(
            public_order_id=public_order_id,
            provider=str(record["provider"]),
            original_reference=str(record["original_reference"]),
            refund_reference=str(record["refund_reference"]),
            amount=Decimal(str(record["amount"])),
            currency=str(record["currency"]),
            refunded_at=datetime.fromisoformat(str(record["refunded_at"])),
            already_processed=already_processed,
        )
