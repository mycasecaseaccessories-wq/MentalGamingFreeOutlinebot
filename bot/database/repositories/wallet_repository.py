"""
WalletRepository — data access for the wallets table.

Manages per-user wallet records.  Balance mutations are always done
via TransactionRepository to maintain the audit ledger.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from decimal import Decimal

from database.models.wallet import WalletORM

from .base import BaseRepository


class WalletRepository(BaseRepository[WalletORM, WalletORM]):
    """
    Handles all database operations for the wallets table.

    Phase 0.2: CRUD inherited; lookup helpers stubbed.
    Phase 3:   WalletService uses get_by_user_id() and adjust_balance().
    """

    orm_class = WalletORM
    domain_class = WalletORM

    async def get_by_user_id(self, user_id: int) -> WalletORM | None:
        """
        Fetch the wallet for the given user.

        Returns:
            WalletORM row, or None if the wallet does not yet exist.
        """
        stmt = select(WalletORM).where(WalletORM.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_update_by_user_id(self, user_id: int) -> WalletORM | None:
        """Load a wallet with a row lock where the database supports it."""
        stmt = select(WalletORM).where(WalletORM.user_id == user_id).with_for_update()
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

    async def debit_if_sufficient(
        self,
        wallet_id: int,
        amount: Decimal,
        *,
        currency: str,
    ) -> WalletORM | None:
        """Reject the legacy direct debit API.

        The conditional debit now lives in ``WalletAccountingService`` so the
        balance update and immutable ledger entry cannot be separated.
        """
        raise RuntimeError(
            "Direct wallet debit is disabled; use WalletAccountingService.debit()."
        )

    async def adjust_balance(self, user_id: int, delta: float) -> WalletORM | None:
        """Reject the legacy direct mutation path.

        Financial changes must go through ``WalletAccountingService`` so that
        validation, a durable ledger row, and idempotency share one boundary.
        """
        raise RuntimeError(
            "Direct wallet balance mutation is disabled; use WalletAccountingService."
        )

    async def freeze(self, user_id: int) -> WalletORM | None:
        """Lock a wallet to prevent debit operations."""
        row = await self.get_by_user_id(user_id)
        if row is None:
            return None
        return await self.update(row.id, is_frozen=True)

    async def unfreeze(self, user_id: int) -> WalletORM | None:
        """Unlock a previously frozen wallet."""
        row = await self.get_by_user_id(user_id)
        if row is None:
            return None
        return await self.update(row.id, is_frozen=False)
