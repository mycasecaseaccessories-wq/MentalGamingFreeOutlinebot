"""
WalletService — in-platform wallet and balance management.

Responsibilities (Phase 3+):
  • Query current wallet balance for a user.
  • Credit balance (top-up via payment gateway).
  • Debit balance (subscription purchase).
  • Transaction history retrieval.
"""

from __future__ import annotations

from .base import BaseService


class WalletService(BaseService):
    """Manages in-platform wallet operations."""

    async def get_balance(self, telegram_id: int) -> float:
        """
        Return the current wallet balance in platform currency units.

        Args:
            telegram_id: Owner of the wallet.
        """
        # TODO (Phase 3): call WalletRepository.get_balance()
        raise NotImplementedError("WalletService.get_balance — Phase 3")

    async def credit(self, telegram_id: int, amount: float, note: str = "") -> None:
        """
        Add funds to a user's wallet.

        Args:
            telegram_id: Recipient user.
            amount:      Positive amount to add.
            note:        Human-readable reason (e.g. payment reference).
        """
        # TODO (Phase 3): create a transaction record, update balance atomically
        raise NotImplementedError("WalletService.credit — Phase 3")

    async def debit(self, telegram_id: int, amount: float, note: str = "") -> None:
        """
        Deduct funds from a user's wallet.

        Raises InsufficientFundsError if balance < amount.
        """
        # TODO (Phase 3): validate balance, create debit transaction atomically
        raise NotImplementedError("WalletService.debit — Phase 3")

    async def get_transactions(self, telegram_id: int, limit: int = 20) -> list:
        """Return the most recent wallet transactions for the user."""
        # TODO (Phase 3): call WalletRepository.list_transactions()
        raise NotImplementedError("WalletService.get_transactions — Phase 3")
