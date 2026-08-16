"""Read-only customer order and payment history service."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.models.history import HistoryPage, OrderHistoryItem, PaymentHistoryItem, PaymentHistoryPage
from database.models.order import OrderORM
from database.models.payment_submission import PaymentSubmissionORM
from database.models.transaction import TransactionORM
from database.models.user import UserORM
from database.models.wallet import WalletORM
from .base import BaseService


class HistoryService(BaseService):
    """Build customer-safe history views without mutating payment state."""

    ORDER_PAGE_SIZE = 5
    PAYMENT_PAGE_SIZE = 5

    async def list_orders(self, telegram_id: int, *, page: int = 1, page_size: int = ORDER_PAGE_SIZE, status: str | None = None) -> HistoryPage:
        page = max(1, int(page)); page_size = min(20, max(1, int(page_size)))
        async with self.db.session() as session:
            filters = [OrderORM.user_id == telegram_id]
            if status:
                filters.append(OrderORM.status == status)
            total = int((await session.execute(select(func.count()).select_from(OrderORM).where(*filters))).scalar_one())
            rows = list((await session.execute(
                select(OrderORM).where(*filters).order_by(OrderORM.created_at.desc(), OrderORM.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )).scalars().all())
        items = tuple(self._order_item(row) for row in rows)
        return HistoryPage(items, page, page_size, total, page > 1, page * page_size < total)

    async def get_order(self, telegram_id: int, public_order_id: str) -> OrderHistoryItem | None:
        async with self.db.session() as session:
            row = (await session.execute(select(OrderORM).where(OrderORM.user_id == telegram_id, OrderORM.public_order_id == public_order_id).limit(1))).scalar_one_or_none()
        return None if row is None else self._order_item(row)

    async def list_payments(self, telegram_id: int, *, page: int = 1, page_size: int = PAYMENT_PAGE_SIZE) -> PaymentHistoryPage:
        page = max(1, int(page)); page_size = min(20, max(1, int(page_size)))
        async with self.db.session() as session:
            manual_rows = list((await session.execute(
                select(PaymentSubmissionORM, OrderORM)
                .join(OrderORM, OrderORM.id == PaymentSubmissionORM.order_id)
                .where(PaymentSubmissionORM.user_id == telegram_id, OrderORM.user_id == telegram_id)
            )).all())
            wallet_rows = list((await session.execute(
                select(TransactionORM, OrderORM)
                .join(WalletORM, WalletORM.id == TransactionORM.wallet_id)
                .join(UserORM, UserORM.id == WalletORM.user_id)
                .outerjoin(OrderORM, OrderORM.id == TransactionORM.order_id)
                .where(UserORM.telegram_id == telegram_id)
            )).all())
            order_rows = list((await session.execute(
                select(OrderORM).where(OrderORM.user_id == telegram_id, OrderORM.payment_method.is_not(None), OrderORM.wallet_transaction_id.is_(None), OrderORM.payment_submission_id.is_(None))
            )).scalars().all())
        items = [self._manual_payment(submission, order) for submission, order in manual_rows]
        items.extend(self._wallet_payment(transaction, order) for transaction, order in wallet_rows)
        items.extend(self._order_payment(order) for order in order_rows)
        items.sort(key=lambda item: (item.created_at, item.payment_id), reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return PaymentHistoryPage(tuple(items[start:start + page_size]), page, page_size, total, page > 1, page * page_size < total)

    @staticmethod
    def _order_item(row: OrderORM) -> OrderHistoryItem:
        return OrderHistoryItem(
            public_order_id=row.public_order_id,
            package_name=row.package_name_snapshot or "Unknown package",
            package_type=row.package_type_snapshot,
            data_limit_gb=row.data_limit_gb_snapshot,
            duration_days=row.duration_days_snapshot,
            device_limit=row.device_limit_snapshot,
            amount=Decimal(str(row.total_amount or row.amount or 0)),
            currency=row.currency,
            status=row.status,
            payment_status=row.payment_status,
            payment_method=row.payment_method,
            payment_reference=row.payment_reference or row.payment_ref,
            created_at=row.created_at,
            paid_at=row.paid_at,
            expires_at=row.expires_at,
        )

    @staticmethod
    def _manual_payment(row: PaymentSubmissionORM, order: OrderORM) -> PaymentHistoryItem:
        return PaymentHistoryItem(
            payment_id=row.public_payment_id,
            order_public_id=order.public_order_id,
            payment_type="manual",
            payment_method=row.payment_method,
            amount=Decimal(str(row.amount)),
            currency=row.currency,
            status=row.status,
            reference=row.transaction_reference,
            created_at=row.submitted_at,
            updated_at=row.reviewed_at or row.updated_at,
            rejection_reason=row.rejection_reason,
        )

    @staticmethod
    def _wallet_payment(row: TransactionORM, order: OrderORM | None) -> PaymentHistoryItem:
        return PaymentHistoryItem(
            payment_id=row.reference or f"WAL-{row.id}",
            order_public_id=order.public_order_id if order else None,
            payment_type="wallet",
            payment_method="wallet",
            amount=Decimal(str(abs(row.amount))),
            currency=row.currency,
            status="paid" if row.type == TransactionORM.TYPE_PURCHASE else row.type,
            reference=row.reference,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _order_payment(row: OrderORM) -> PaymentHistoryItem:
        return PaymentHistoryItem(
            payment_id=row.payment_reference or row.payment_ref or row.public_order_id,
            order_public_id=row.public_order_id,
            payment_type="order",
            payment_method=row.payment_method,
            amount=Decimal(str(row.total_amount or row.amount or 0)),
            currency=row.currency,
            status=row.payment_status,
            reference=row.payment_reference or row.payment_ref,
            created_at=row.paid_at or row.created_at,
            updated_at=row.paid_at,
        )
