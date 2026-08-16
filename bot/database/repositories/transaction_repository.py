"""Read-only transaction data access used by Phase 1.3 customer wallet UI."""

from __future__ import annotations

from sqlalchemy import func, select

from database.models.transaction import TransactionORM
from .base import BaseRepository


class TransactionRepository(BaseRepository[TransactionORM, TransactionORM]):
    orm_class = TransactionORM
    domain_class = TransactionORM

    async def list_by_wallet(
        self,
        wallet_id: int,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> list[TransactionORM]:
        stmt = (
            select(TransactionORM)
            .where(TransactionORM.wallet_id == wallet_id)
            .order_by(TransactionORM.created_at.desc(), TransactionORM.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_idempotency_key(self, idempotency_key: str) -> TransactionORM | None:
        """Return the immutable ledger row for a previously handled payment."""
        stmt = select(TransactionORM).where(
            TransactionORM.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: int) -> list[TransactionORM]:
        """Return ledger rows linked to an order, newest first."""
        stmt = (
            select(TransactionORM)
            .where(TransactionORM.order_id == order_id)
            .order_by(TransactionORM.created_at.desc(), TransactionORM.id.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_wallet(self, wallet_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(TransactionORM)
            .where(TransactionORM.wallet_id == wallet_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
