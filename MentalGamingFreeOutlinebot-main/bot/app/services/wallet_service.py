"""Customer wallet read model for Phase 1.3.

Phase 1.3 deliberately exposes read-only wallet operations. Real credits,
debits, top-ups and payment mutations are implemented in Phase 2.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.customer_account import TransactionPage, TransactionSummary, WalletSummary
from database.repositories.transaction_repository import TransactionRepository
from database.repositories.user_repository import UserRepository
from database.repositories.wallet_repository import WalletRepository
from .base import BaseService


class WalletService(BaseService):
    """Read-only customer wallet service for Phase 1.3."""

    async def get_or_create_wallet(
        self,
        telegram_id: int,
        *,
        currency: str = "MMK",
    ) -> WalletSummary:
        if telegram_id <= 0:
            raise ValueError("telegram_id must be positive")
        currency = (currency or "MMK").upper()[:8]

        async with self.db.session() as session:
            users = UserRepository(session)
            user = await users.get_by_telegram_id(telegram_id)
            if user is None:
                raise LookupError("User not found")

            wallets = WalletRepository(session)
            row = await wallets.get_or_create(user.id, currency=currency)

        return WalletSummary(
            wallet_id=row.id,
            balance=Decimal(str(row.balance)),
            currency=row.currency,
            is_frozen=bool(row.is_frozen),
        )

    async def get_balance(self, telegram_id: int, *, currency: str = "MMK") -> Decimal:
        """Return current balance without mutating it."""
        wallet = await self.get_or_create_wallet(telegram_id, currency=currency)
        return wallet.balance

    async def get_wallet_summary(
        self,
        telegram_id: int,
        *,
        currency: str = "MMK",
    ) -> WalletSummary:
        return await self.get_or_create_wallet(telegram_id, currency=currency)

    async def get_transaction_history(
        self,
        telegram_id: int,
        *,
        page: int = 1,
        page_size: int = 5,
        currency: str = "MMK",
    ) -> TransactionPage:
        page = max(1, int(page))
        page_size = min(20, max(1, int(page_size)))
        wallet = await self.get_or_create_wallet(telegram_id, currency=currency)

        async with self.db.session() as session:
            repo = TransactionRepository(session)
            total = await repo.count_by_wallet(wallet.wallet_id)
            rows = await repo.list_by_wallet(
                wallet.wallet_id,
                limit=page_size,
                offset=(page - 1) * page_size,
            )

        items = tuple(
            TransactionSummary(
                transaction_id=row.id,
                amount=Decimal(str(row.amount)),
                currency=row.currency,
                type=row.type,
                reference=row.reference,
                note=row.note,
                created_at=row.created_at,
            )
            for row in rows
        )
        return TransactionPage(
            items=items,
            page=page,
            page_size=page_size,
            has_previous=page > 1,
            has_next=(page * page_size) < total,
        )

    async def get_transactions(self, telegram_id: int, limit: int = 20) -> list[TransactionSummary]:
        """Backward-compatible read alias."""
        page = await self.get_transaction_history(
            telegram_id,
            page=1,
            page_size=min(20, max(1, limit)),
        )
        return list(page.items)

    async def credit(self, telegram_id: int, amount, note: str = "") -> None:
        raise NotImplementedError("Wallet credit is intentionally disabled until Phase 2")

    async def debit(self, telegram_id: int, amount, note: str = "") -> None:
        raise NotImplementedError("Wallet debit is intentionally disabled until Phase 2")
