"""Admin manual-payment review workflow for Phase 2.4."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.result import Failure, Result, Success
from app.services.admin_authorization_service import AdminAuthorizationService
from app.events import EventType, bus
from app.models.payment_review import PaymentReviewDecision, PaymentReviewItem, PaymentReviewPage
from locales.translator import t
from database.models.audit_log import AuditLogORM
from database.models.notification import NotificationORM
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.user import UserORM
from database.repositories.order_repository import OrderRepository
from database.repositories.payment_submission_repository import PaymentSubmissionRepository
from .base import BaseService
from .manual_payment_service import ManualPaymentService
from .order_service import InvalidOrderStateError, OrderService


class PaymentReviewService(BaseService):
    """Authoritative admin review transitions; approval never provisions VPN."""

    PAGE_SIZE = 10

    def __init__(self, db=None, *, manual_payment_service: ManualPaymentService | None = None) -> None:
        super().__init__(db)
        self.manual_payment_service = manual_payment_service or ManualPaymentService(db)

    async def list_pending(self, *, page: int = 1, page_size: int = PAGE_SIZE) -> PaymentReviewPage:
        return await self.list_by_status(
            status=PaymentSubmissionORM.STATUS_PENDING_REVIEW,
            page=page,
            page_size=page_size,
        )

    async def list_by_status(self, *, status: str, page: int = 1, page_size: int = PAGE_SIZE) -> PaymentReviewPage:
        page = max(1, page)
        page_size = max(1, min(50, page_size))
        async with self.db.session() as session:
            repo = PaymentSubmissionRepository(session)
            total = await repo.count_by_status(status)
            rows = await repo.list_with_context(status=status, offset=(page - 1) * page_size, limit=page_size)
            items = [self._item(submission, order, user) for submission, order, user in rows]
        return PaymentReviewPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_previous=page > 1,
            has_next=page * page_size < total,
        )

    async def get_detail(self, *, public_payment_id: str) -> PaymentReviewItem | None:
        async with self.db.session() as session:
            row = await PaymentSubmissionRepository(session).get_with_context(public_payment_id)
            if row is None:
                return None
            return self._item(*row)

    async def approve(self, *, actor_telegram_id: int, public_payment_id: str, request_id: str | None = None) -> Result[PaymentReviewDecision]:
        return await self._decide(
            actor_telegram_id=actor_telegram_id,
            public_payment_id=public_payment_id,
            decision=PaymentSubmissionORM.STATUS_APPROVED,
            reason=None,
            request_id=request_id,
        )

    async def reject(self, *, actor_telegram_id: int, public_payment_id: str, reason: str, request_id: str | None = None) -> Result[PaymentReviewDecision]:
        cleaned = " ".join((reason or "").split())[:500]
        if not cleaned:
            return Failure("rejection_reason_required", "A rejection reason is required.")
        return await self._decide(
            actor_telegram_id=actor_telegram_id,
            public_payment_id=public_payment_id,
            decision=PaymentSubmissionORM.STATUS_REJECTED,
            reason=cleaned,
            request_id=request_id,
        )

    async def _decide(self, *, actor_telegram_id: int, public_payment_id: str, decision: str, reason: str | None, request_id: str | None) -> Result[PaymentReviewDecision]:
        event_type = EventType.MANUAL_PAYMENT_APPROVED if decision == PaymentSubmissionORM.STATUS_APPROVED else EventType.MANUAL_PAYMENT_REJECTED
        event_payload: dict[str, object] | None = None
        async with self.db.session() as session:
            actor = (await session.execute(
                select(UserORM).where(UserORM.telegram_id == actor_telegram_id).limit(1)
            )).scalar_one_or_none()
            if actor is None or not await AdminAuthorizationService(self.db).has_permission_for_user(actor.id, "manage_payments"):
                return Failure("unauthorized", "Admin permission required.")

            repo = PaymentSubmissionRepository(session)
            submission = await repo.get_for_update_by_public_payment_id(public_payment_id)
            if submission is None:
                return Failure("not_found", "Payment submission not found.")
            if submission.status != PaymentSubmissionORM.STATUS_PENDING_REVIEW:
                return Success(PaymentReviewDecision(
                    public_payment_id=submission.public_payment_id,
                    public_order_id="",
                    decision=submission.status,
                    status=submission.status,
                    already_decided=True,
                ))

            order_public_id = (await session.execute(
                select(OrderORM.public_order_id).where(OrderORM.id == submission.order_id).limit(1)
            )).scalar_one_or_none()
            order = None if order_public_id is None else await OrderRepository(session).get_for_update_by_public_order_id(order_public_id)
            if order is None or order.id != submission.order_id or order.user_id != submission.user_id:
                return Failure("invalid_order", "The linked order is invalid.")
            if order.payment_submission_id not in {None, submission.id}:
                return Failure("payment_conflict", "The order is linked to another payment submission.")
            if order.status in {OrderORM.STATUS_PAID, OrderORM.STATUS_COMPLETED, OrderORM.STATUS_CANCELLED, OrderORM.STATUS_REFUNDED}:
                return Failure("invalid_order_state", "The order cannot be reviewed in its current state.")
            if order.total_amount != submission.amount or order.currency != submission.currency:
                return Failure("amount_or_currency_mismatch", "Payment amount or currency does not match the order.")
            method = await self.manual_payment_service.get_method(
                submission.payment_method,
                amount=order.total_amount,
                currency=order.currency,
            )
            if method is None:
                return Failure("manual_method_unavailable", "The payment method is no longer available.")

            now = datetime.now(timezone.utc)
            submitted_before_expiry = order.expires_at is None or _as_utc(submission.submitted_at) <= _as_utc(order.expires_at)
            if not submitted_before_expiry:
                return Failure("submitted_after_expiry", "This payment was submitted after the order expired.")

            target_order_status = None
            try:
                if decision == PaymentSubmissionORM.STATUS_APPROVED:
                    OrderService.validate_transition(order.status, OrderORM.STATUS_PAID)
                else:
                    target_order_status = (
                        OrderORM.STATUS_EXPIRED
                        if order.expires_at is not None and _as_utc(order.expires_at) <= now
                        else OrderORM.STATUS_WAITING_PAYMENT
                    )
                    if target_order_status != OrderORM.STATUS_EXPIRED:
                        OrderService.validate_transition(order.status, target_order_status)
            except InvalidOrderStateError:
                return Failure("invalid_order_state", "The order cannot be changed in its current state.")

            old_submission = {"status": submission.status, "reviewed_by": submission.reviewed_by}
            old_order = {"status": order.status, "payment_status": order.payment_status}
            claim_values = {
                "status": decision,
                "reviewed_at": now,
                "reviewed_by": actor_telegram_id,
                "approved_at": now if decision == PaymentSubmissionORM.STATUS_APPROVED else None,
                "rejected_at": now if decision == PaymentSubmissionORM.STATUS_REJECTED else None,
                "rejection_reason": reason,
            }
            claim = await session.execute(
                update(PaymentSubmissionORM)
                .where(
                    PaymentSubmissionORM.id == submission.id,
                    PaymentSubmissionORM.status == PaymentSubmissionORM.STATUS_PENDING_REVIEW,
                )
                .values(**claim_values)
            )
            if claim.rowcount != 1:
                await session.rollback()
                fresh = await repo.get_by_public_payment_id(public_payment_id)
                return Success(PaymentReviewDecision(
                    public_payment_id=public_payment_id,
                    public_order_id=order.public_order_id,
                    decision=fresh.status if fresh else decision,
                    status=fresh.status if fresh else decision,
                    already_decided=True,
                ))
            submission.status = decision
            submission.reviewed_at = now
            submission.reviewed_by = actor_telegram_id
            submission.approved_at = claim_values["approved_at"]
            submission.rejected_at = claim_values["rejected_at"]
            submission.rejection_reason = reason
            order.payment_submission_id = submission.id
            order.payment_method = submission.payment_method
            order.payment_reference = submission.transaction_reference
            order.payment_ref = submission.transaction_reference
            order.metadata_json = {**(order.metadata_json or {}), "review_request_id": request_id} if request_id else order.metadata_json

            customer = (await session.execute(
                select(UserORM).where(UserORM.telegram_id == order.user_id).limit(1)
            )).scalar_one_or_none()
            customer_language = getattr(customer, "language", None) or "en"
            if hasattr(customer_language, "value"):
                customer_language = customer_language.value
            if customer_language not in {"en", "my"}:
                customer_language = "en"

            if decision == PaymentSubmissionORM.STATUS_APPROVED:
                submission.status = PaymentSubmissionORM.STATUS_APPROVED
                order.status = OrderORM.STATUS_PAID
                order.payment_status = OrderORM.PAYMENT_PAID
                order.approved_by = actor_telegram_id
                order.approved_at = now
                order.paid_at = now
                audit_action = "manual_payment.approved"
                notification_type = "manual_payment_approved"
                subject = f"Payment approved: {submission.public_payment_id}"
                body = t("notification.manual_payment_approved", language=customer_language, order=order.public_order_id)
            else:
                submission.status = PaymentSubmissionORM.STATUS_REJECTED
                order.status = target_order_status
                order.payment_status = OrderORM.PAYMENT_UNPAID
                order.rejected_at = now
                order.rejection_reason = reason
                audit_action = "manual_payment.rejected"
                notification_type = "manual_payment_rejected"
                subject = f"Payment rejected: {submission.public_payment_id}"
                body = t("notification.manual_payment_rejected", language=customer_language, order=order.public_order_id, reason=reason)

            session.add(AuditLogORM(
                actor_id=actor_telegram_id,
                action=audit_action,
                entity_type="PaymentSubmission",
                entity_id=submission.id,
                old_value=json.dumps({"submission": old_submission, "order": old_order}, sort_keys=True),
                new_value=json.dumps({"submission_status": submission.status, "order_status": order.status, "payment_status": order.payment_status, "reason": reason}, sort_keys=True),
                note=f"Phase 2.4 admin decision request_id={request_id or 'none'} payment={submission.public_payment_id} order={order.public_order_id}",
            ))
            session.add(NotificationORM(
                user_id=order.user_id,
                type=notification_type,
                channel="telegram",
                subject=subject,
                body=body,
                status=NotificationORM.STATUS_QUEUED,
            ))
            await session.flush()
            event_payload = {
                "actor_telegram_id": actor_telegram_id,
                "public_payment_id": submission.public_payment_id,
                "public_order_id": order.public_order_id,
                "decision": decision,
                "request_id": request_id,
                "order_id": order.id,
                "user_id": order.user_id,
                "payment_status": "paid" if decision == PaymentSubmissionORM.STATUS_APPROVED else "unpaid",
                "payment_reference": submission.transaction_reference,
            }
            result = PaymentReviewDecision(
                public_payment_id=submission.public_payment_id,
                public_order_id=order.public_order_id,
                decision=decision,
                status=submission.status,
            )

        if event_payload is not None:
            await bus.emit(event_type, **event_payload)
            await bus.emit(EventType.PAYMENT_REVIEW_COMPLETED, **event_payload)
            if event_payload.get("payment_status") == "paid":
                await bus.emit(EventType.ORDER_PAID, **event_payload)
        return Success(result)

    @staticmethod
    def _item(submission, order, user) -> PaymentReviewItem:
        return PaymentReviewItem(
            public_payment_id=submission.public_payment_id,
            public_order_id=order.public_order_id,
            user_id=submission.user_id,
            telegram_id=user.telegram_id,
            username=user.username,
            customer_name=user.full_name,
            payment_method=submission.payment_method,
            amount=submission.amount,
            currency=submission.currency,
            transaction_reference=submission.transaction_reference,
            proof_file_id=submission.proof_file_id,
            proof_file_unique_id=submission.proof_file_unique_id,
            proof_file_type=submission.proof_file_type,
            status=submission.status,
            submitted_at=submission.submitted_at,
            order_status=order.status,
            order_payment_status=order.payment_status,
        )


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
