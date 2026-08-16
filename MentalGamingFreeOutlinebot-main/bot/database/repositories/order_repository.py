"""Database-only repository for Phase 2.1 orders."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select

from database.models.order import OrderORM
from .base import BaseRepository


class OrderRepository(BaseRepository[OrderORM, OrderORM]):
    """Persistence operations; business transitions stay in OrderService."""

    orm_class = OrderORM
    domain_class = OrderORM

    async def get_by_public_order_id(self, public_order_id: str) -> Optional[OrderORM]:
        stmt = select(OrderORM).where(OrderORM.public_order_id == public_order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update_by_public_order_id(self, public_order_id: str) -> Optional[OrderORM]:
        """Load an order with a database row lock for payment transitions."""
        stmt = (
            select(OrderORM)
            .where(OrderORM.public_order_id == public_order_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_checkout_token(self, checkout_token: str) -> Optional[OrderORM]:
        stmt = select(OrderORM).where(OrderORM.checkout_token == checkout_token)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int, public_order_id: str) -> Optional[OrderORM]:
        """Load an order only when both public ID and owner match."""
        stmt = select(OrderORM).where(
            OrderORM.user_id == user_id,
            OrderORM.public_order_id == public_order_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int, limit: int = 20) -> List[OrderORM]:
        stmt = (
            select(OrderORM)
            .where(OrderORM.user_id == user_id)
            .order_by(OrderORM.created_at.desc())
            .limit(max(1, min(100, limit)))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_open_order(self, user_id: int, checkout_token: str) -> Optional[OrderORM]:
        stmt = select(OrderORM).where(
            OrderORM.user_id == user_id,
            OrderORM.checkout_token == checkout_token,
            OrderORM.status.in_((OrderORM.STATUS_PENDING, OrderORM.STATUS_WAITING_PAYMENT)),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str) -> List[OrderORM]:
        stmt = select(OrderORM).where(OrderORM.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_expirable(self, now: datetime) -> List[OrderORM]:
        stmt = select(OrderORM).where(
            OrderORM.status.in_((OrderORM.STATUS_PENDING, OrderORM.STATUS_WAITING_PAYMENT)),
            OrderORM.expires_at.is_not(None),
            OrderORM.expires_at <= now,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(OrderORM).where(OrderORM.user_id == user_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def update_status(self, order_id: int, status: str, **fields) -> Optional[OrderORM]:
        return await self.update(order_id, status=status, **fields)

    async def mark_cancelled(self, order_id: int, cancelled_at: datetime, note: str | None = None) -> Optional[OrderORM]:
        fields = {"status": OrderORM.STATUS_CANCELLED, "cancelled_at": cancelled_at}
        if note:
            fields["notes"] = note
        return await self.update(order_id, **fields)

    async def mark_expired(self, order_id: int, *, now: datetime) -> Optional[OrderORM]:
        return await self.update_status(order_id, OrderORM.STATUS_EXPIRED, expires_at=now)

    # Backward-compatible aliases used by earlier phases.
    async def get_orders_for_user(self, user_id: int, limit: int = 20) -> List[OrderORM]:
        return await self.list_by_user(user_id, limit)

    async def get_by_payment_ref(self, payment_ref: str) -> Optional[OrderORM]:
        stmt = select(OrderORM).where(
            (OrderORM.payment_ref == payment_ref) | (OrderORM.payment_reference == payment_ref)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_paid(self, order_id: int, payment_ref: str) -> Optional[OrderORM]:
        return await self.update_status(
            order_id,
            OrderORM.STATUS_PAID,
            payment_ref=payment_ref,
            payment_reference=payment_ref,
            payment_status=OrderORM.PAYMENT_PAID,
        )

    async def mark_fulfilled(self, order_id: int, vpn_key_id: int) -> Optional[OrderORM]:
        return await self.update_status(
            order_id, OrderORM.STATUS_COMPLETED, vpn_key_id=vpn_key_id,
        )

    async def cancel(self, order_id: int, note: str = "") -> Optional[OrderORM]:
        from datetime import timezone
        return await self.mark_cancelled(
            order_id,
            datetime.now(timezone.utc),
            note or None,
        )
