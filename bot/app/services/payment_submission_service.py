"""Phase 2.3 manual payment submission service."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.models.manual_payment import ManualPaymentMethod
from app.models.payment_submission import PaymentSubmissionReceipt
from config import settings
from database.models.notification import NotificationORM
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.repositories.payment_submission_repository import PaymentSubmissionRepository
from .base import BaseService
from .manual_payment_service import ManualPaymentService
from .maintenance_service import MaintenanceBlockedError, MaintenanceService


class PaymentSubmissionService(BaseService):
    """Creates manual-payment submissions without approving or provisioning."""

    def __init__(
        self,
        db=None,
        *,
        manual_payment_service: ManualPaymentService | None = None,
        maintenance_service: MaintenanceService | None = None,
    ) -> None:
        super().__init__(db)
        self.manual_payment_service = manual_payment_service or ManualPaymentService(db)
        self.maintenance_service = maintenance_service

    async def submit(
        self,
        *,
        user_id: int,
        public_order_id: str,
        method_id: str,
        transaction_reference: str | None = None,
        proof_file_id: str | None = None,
        proof_file_unique_id: str | None = None,
        proof_file_type: str | None = None,
    ) -> Result[PaymentSubmissionReceipt]:
        """Persist one pending-review submission in a single DB transaction."""
        if self.maintenance_service is not None:
            try:
                await self.maintenance_service.assert_operation_allowed("payments", "CREATE")
            except MaintenanceBlockedError:
                return Failure("maintenance_active", "New payment submissions are temporarily unavailable during maintenance.")
        reference = _clean(transaction_reference, 256)
        proof_file_id = _clean(proof_file_id, 256)
        proof_file_unique_id = _clean(proof_file_unique_id, 256)
        proof_file_type = _clean(proof_file_type, 32)
        if not reference and not proof_file_id:
            return Failure("proof_required", "A transaction reference or payment proof is required.")

        method = await self.manual_payment_service.get_method(method_id)
        if method is None:
            return Failure("manual_method_unavailable", "The selected payment method is unavailable.")

        async with self.db.session() as session:
            from sqlalchemy import select

            order_result = await session.execute(
                select(OrderORM).where(
                    OrderORM.public_order_id == public_order_id,
                    OrderORM.user_id == user_id,
                ).limit(1)
            )
            order = order_result.scalar_one_or_none()
            if order is None:
                return Failure("order_not_found", "Order not found.")
            if order.status in {OrderORM.STATUS_PAID, OrderORM.STATUS_COMPLETED} or order.payment_status == OrderORM.PAYMENT_PAID:
                return Failure("already_paid", "This order is already paid.")
            if order.status in {OrderORM.STATUS_CANCELLED, OrderORM.STATUS_EXPIRED}:
                return Failure("order_expired", "This order cannot accept payment proof.")
            now = datetime.now(timezone.utc)
            if _is_expired(order.expires_at, now):
                return Failure("order_expired", "This order has expired.")
            if order.currency != method.currency:
                return Failure("currency_mismatch", "Payment method currency does not match the order.")
            if method.min_amount is not None and order.total_amount < method.min_amount:
                return Failure("amount_out_of_range", "Order amount is below the payment method minimum.")
            if method.max_amount is not None and order.total_amount > method.max_amount:
                return Failure("amount_out_of_range", "Order amount exceeds the payment method maximum.")

            repo = PaymentSubmissionRepository(session)
            idempotency_key = _idempotency_key(
                order.id,
                method.method_id,
                reference,
                proof_file_unique_id or proof_file_id,
            )
            existing = await repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return Success(_receipt(existing, public_order_id, duplicate=True))

            pending = await repo.list_for_order(order.id)
            for submission in pending:
                if submission.status == PaymentSubmissionORM.STATUS_PENDING_REVIEW:
                    return Failure("review_pending", "A payment submission is already awaiting review.")

            public_payment_id = _public_payment_id()
            row = PaymentSubmissionORM(
                public_payment_id=public_payment_id,
                idempotency_key=idempotency_key,
                order_id=order.id,
                user_id=user_id,
                payment_method=method.method_id,
                amount=order.total_amount,
                currency=order.currency,
                transaction_reference=reference,
                proof_file_id=proof_file_id,
                proof_file_unique_id=proof_file_unique_id,
                proof_file_type=proof_file_type,
                status=PaymentSubmissionORM.STATUS_PENDING_REVIEW,
                submitted_at=now,
                metadata_json={"source": "telegram", "review_required": True},
            )
            session.add(row)
            await session.flush()

            # Crucial boundary: submission is not approval and never becomes Paid.
            order.status = OrderORM.STATUS_AWAITING_APPROVAL
            order.payment_status = OrderORM.PAYMENT_UNDER_REVIEW
            order.payment_method = method.method_id
            order.payment_submission_id = row.id
            await session.flush()

            for admin_id in settings.admin_ids:
                session.add(NotificationORM(
                    user_id=admin_id,
                    type="manual_payment_submitted",
                    channel="telegram",
                    subject=f"Manual payment review: {public_payment_id}",
                    body=(
                        f"Payment {public_payment_id} for order {public_order_id} "
                        f"is awaiting admin review. Amount: {order.total_amount} {order.currency}."
                    ),
                    status=NotificationORM.STATUS_QUEUED,
                ))

            receipt = PaymentSubmissionReceipt(
                public_payment_id=public_payment_id,
                public_order_id=public_order_id,
                status=PaymentSubmissionORM.STATUS_PENDING_REVIEW,
                amount=order.total_amount,
                currency=order.currency,
                payment_method=method.method_id,
                submitted_at=now,
            )

        await bus.emit(
            EventType.MANUAL_PAYMENT_SUBMITTED,
            user_id=user_id,
            public_order_id=public_order_id,
            public_payment_id=receipt.public_payment_id,
            amount=str(receipt.amount),
            currency=receipt.currency,
        )
        return Success(receipt)


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        return expires_at <= now.replace(tzinfo=None)
    return expires_at <= now


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value[:limit] or None


def _idempotency_key(
    order_id: int,
    method_id: str,
    reference: str | None,
    proof_identity: str | None,
) -> str:
    raw = "|".join((str(order_id), method_id, reference or "", proof_identity or ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _public_payment_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"PAY-{stamp}-{secrets.token_urlsafe(5).upper().replace('-', 'A').replace('_', 'B')}"


def _receipt(row, public_order_id: str, *, duplicate: bool) -> PaymentSubmissionReceipt:
    return PaymentSubmissionReceipt(
        public_payment_id=row.public_payment_id,
        public_order_id=public_order_id,
        status=row.status,
        amount=Decimal(str(row.amount)),
        currency=row.currency,
        payment_method=row.payment_method,
        submitted_at=row.submitted_at,
        duplicate=duplicate,
    )
