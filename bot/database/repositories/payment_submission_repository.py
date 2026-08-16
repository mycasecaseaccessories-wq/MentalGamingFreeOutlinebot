"""Repository for manual payment submissions."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.payment_submission import PaymentSubmission
from database.models.payment_submission import PaymentSubmissionORM
from database.models.order import OrderORM
from database.models.user import UserORM
from .base import BaseRepository


class PaymentSubmissionRepository(BaseRepository[PaymentSubmissionORM, PaymentSubmission]):
    orm_class = PaymentSubmissionORM
    domain_class = PaymentSubmission

    def _to_domain(self, row: PaymentSubmissionORM) -> PaymentSubmission:
        return PaymentSubmission(
            id=row.id,
            public_payment_id=row.public_payment_id,
            order_id=row.order_id,
            user_id=row.user_id,
            payment_method=row.payment_method,
            amount=row.amount,
            currency=row.currency,
            status=row.status,
            transaction_reference=row.transaction_reference,
            proof_file_id=row.proof_file_id,
            proof_file_unique_id=row.proof_file_unique_id,
            proof_file_type=row.proof_file_type,
            submitted_at=row.submitted_at,
        )

    async def get_by_idempotency_key(self, key: str) -> PaymentSubmission | None:
        result = await self._session.execute(
            select(PaymentSubmissionORM).where(
                PaymentSubmissionORM.idempotency_key == key,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def get_for_owner(
        self,
        *,
        public_payment_id: str,
        user_id: int,
    ) -> PaymentSubmission | None:
        result = await self._session.execute(
            select(PaymentSubmissionORM).where(
                PaymentSubmissionORM.public_payment_id == public_payment_id,
                PaymentSubmissionORM.user_id == user_id,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def get_by_public_payment_id(self, public_payment_id: str) -> PaymentSubmissionORM | None:
        result = await self._session.execute(
            select(PaymentSubmissionORM).where(
                PaymentSubmissionORM.public_payment_id == public_payment_id,
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_for_update_by_public_payment_id(self, public_payment_id: str) -> PaymentSubmissionORM | None:
        result = await self._session.execute(
            select(PaymentSubmissionORM)
            .where(PaymentSubmissionORM.public_payment_id == public_payment_id)
            .with_for_update()
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_by_status(self, status: str) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(PaymentSubmissionORM).where(
                PaymentSubmissionORM.status == status,
            )
        )
        return int(result.scalar_one())

    async def count_pending(self) -> int:
        return await self.count_by_status(PaymentSubmissionORM.STATUS_PENDING_REVIEW)

    async def list_with_context(self, *, status: str, offset: int, limit: int):
        result = await self._session.execute(
            select(PaymentSubmissionORM, OrderORM, UserORM)
            .join(OrderORM, OrderORM.id == PaymentSubmissionORM.order_id)
            .join(UserORM, UserORM.telegram_id == PaymentSubmissionORM.user_id)
            .where(PaymentSubmissionORM.status == status)
            .order_by(PaymentSubmissionORM.submitted_at.desc(), PaymentSubmissionORM.id.desc())
            .offset(max(0, offset))
            .limit(max(1, min(50, limit)))
        )
        return list(result.all())

    async def list_pending_with_context(self, *, offset: int, limit: int):
        return await self.list_with_context(
            status=PaymentSubmissionORM.STATUS_PENDING_REVIEW,
            offset=offset,
            limit=limit,
        )

    async def get_with_context(self, public_payment_id: str):
        result = await self._session.execute(
            select(PaymentSubmissionORM, OrderORM, UserORM)
            .join(OrderORM, OrderORM.id == PaymentSubmissionORM.order_id)
            .join(UserORM, UserORM.telegram_id == PaymentSubmissionORM.user_id)
            .where(PaymentSubmissionORM.public_payment_id == public_payment_id)
            .limit(1)
        )
        return result.first()

    async def list_for_order(self, order_id: int) -> list[PaymentSubmission]:
        result = await self._session.execute(
            select(PaymentSubmissionORM)
            .where(PaymentSubmissionORM.order_id == order_id)
            .order_by(PaymentSubmissionORM.created_at.desc())
        )
        return [self._to_domain(row) for row in result.scalars().all()]
