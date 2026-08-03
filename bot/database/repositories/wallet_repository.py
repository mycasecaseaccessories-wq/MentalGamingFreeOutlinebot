"""
WalletRepository — data access for the wallets table.

Manages per-user wallet records.  Balance mutations are always done
via TransactionRepository to maintain the audit ledger.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from database.models.wallet import WalletORM
from .base import BaseRepository


class WalletRepository(BaseRepository[WalletORM, WalletORM]):
    """
    Handles all database operations for the wallets table.

    Phase 0.2: CRUD inherited; lookup helpers stubbed.
    Phase 3:   WalletService uses get_by_user_id() and adjust_balance().
    """

    orm_class    = WalletORM
    domain_class = WalletORM

    async def get_by_user_id(self, user_id: int) -> Optional[WalletORM]:
        """
        Fetch the wallet for the given user.

        Returns:
            WalletORM row, or None if the wallet does not yet exist.
        """
        stmt = select(WalletORM).where(WalletORM.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int, currency: str = "USD") -> WalletORM:
        """
        Return the existing wallet or create a zero-balance one.

        Args:
            user_id:  Owner user primary key.
            currency: ISO 4217 currency code for the wallet (default USD).
        """
        row = await self.get_by_user_id(user_id)
        if row is not None:
            return row
        return await self.create(user_id=user_id, currency=currency, balance=0.0)  # type: ignore[return-value]

    async def adjust_balance(self, user_id: int, delta: float) -> Optional[WalletORM]:
        """
        Add delta to the wallet balance (delta < 0 for debits).

        IMPORTANT: Always call this inside a transaction that also creates a
        TransactionORM record — never adjust balance without a ledger entry.

        Args:
            user_id: Owner user primary key.
            delta:   Amount to add (positive) or subtract (negative).

        Returns:
            Updated WalletORM, or None if wallet not found.
        """
        row = await self.get_by_user_id(user_id)
        if row is None:
            return None
        row.balance = float(row.balance) + delta
        await self._session.flush()
        return row

    async def freeze(self, user_id: int) -> Optional[WalletORM]:
        """Lock a wallet to prevent debit operations."""
        row = await self.get_by_user_id(user_id)
        if row is None:
            return None
        return await self.update(row.id, is_frozen=True)

    async def unfreeze(self, user_id: int) -> Optional[WalletORM]:
        """Unlock a previously frozen wallet."""
        row = await self.get_by_user_id(user_id)
        if row is None:
            return None
        return await self.update(row.id, is_frozen=False)
