"""
OrderRepository — data access for the orders table.

Tracks purchase orders through their lifecycle: pending → paid → fulfilled.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models.order import OrderORM
from .base import BaseRepository


class OrderRepository(BaseRepository[OrderORM, OrderORM]):
    """
    Handles all database operations for the orders table.

    Phase 0.2: CRUD inherited; lifecycle queries stubbed.
    Phase 3:   order placement, payment confirmation, and fulfilment.
    """

    orm_class    = OrderORM
    domain_class = OrderORM

    async def get_orders_for_user(
        self, user_id: int, limit: int = 20
    ) -> List[OrderORM]:
        """
        Return the most recent orders for a user, newest first.

        Args:
            user_id: Owner user primary key.
            limit:   Maximum number of orders to return.
        """
        stmt = (
            select(OrderORM)
            .where(OrderORM.user_id == user_id)
            .order_by(OrderORM.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> List[OrderORM]:
        """Return all orders with the given status (e.g. "pending", "paid")."""
        stmt = select(OrderORM).where(OrderORM.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_payment_ref(self, payment_ref: str) -> Optional[OrderORM]:
        """Look up an order by its external payment gateway transaction ID."""
        stmt = select(OrderORM).where(OrderORM.payment_ref == payment_ref)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_paid(self, order_id: int, payment_ref: str) -> Optional[OrderORM]:
        """Transition an order from pending to paid."""
        return await self.update(
            order_id,
            status=OrderORM.STATUS_PAID,
            payment_ref=payment_ref,
        )

    async def mark_fulfilled(self, order_id: int, vpn_key_id: int) -> Optional[OrderORM]:
        """Mark an order as fulfilled and link the issued VPN key."""
        return await self.update(
            order_id,
            status=OrderORM.STATUS_FULFILLED,
            vpn_key_id=vpn_key_id,
        )

    async def cancel(self, order_id: int, note: str = "") -> Optional[OrderORM]:
        """Cancel an order."""
        return await self.update(
            order_id,
            status=OrderORM.STATUS_CANCELLED,
            notes=note or None,
        )
