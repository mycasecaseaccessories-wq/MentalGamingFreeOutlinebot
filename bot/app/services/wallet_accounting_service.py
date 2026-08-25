"""Authoritative wallet accounting boundary for Phase 8.3.

All balance-changing operations must use this service. It validates money as
positive finite Decimal values, checks currency/freeze state, and writes the
ledger entry in the same database transaction as the balance update.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.result import Failure, Result, Success
from database.models.transaction import TransactionORM
from database.models.wallet import WalletORM
from database.repositories.wallet_repository import WalletRepository

from .base import BaseService


@dataclass(frozen=True, slots=True)
class AccountingReceipt:
    wallet_id: int
    user_id: int
    transaction_id: int
    amount: Decimal
    currency: str
    direction: str
    source_type: str
    source_reference: str
    idempotent: bool = False


class WalletAccountingService(BaseService):
    """Single authoritative boundary for wallet credits and debits."""

    async def credit(
        self,
        *,
        user_id: int,
        amount: Decimal | int | str,
        currency: str,
        source_type: str,
        source_reference: str,
        idempotency_key: str,
        note: str | None = None,
    ) -> Result[AccountingReceipt]:
        return await self._apply(
            user_id=user_id,
            amount=amount,
            currency=currency,
            direction="credit",
            transaction_type=TransactionORM.TYPE_TOP_UP,
            source_type=source_type,
            source_reference=source_reference,
            idempotency_key=idempotency_key,
            note=note,
        )

    async def credit_in_session(  # noqa: PLR0911
        self,
        session: Any,
        *,
        user_id: int,
        amount: Decimal | int | str,
        currency: str,
        source_type: str,
        source_reference: str,
        idempotency_key: str,
        transaction_type: str = TransactionORM.TYPE_BONUS,
        note: str | None = None,
    ) -> Result[AccountingReceipt]:
        """Credit using a caller-owned transaction/session."""
        validated = self._validate(amount, currency, source_type, source_reference, idempotency_key)
        if validated.is_failure:
            return validated
        value, normalized_currency = validated.unwrap()
        prior = (
            await session.execute(
                select(TransactionORM).where(TransactionORM.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if prior is not None:
            wallet = await session.get(WalletORM, prior.wallet_id)
            if wallet is None or wallet.user_id != user_id:
                return Failure("idempotency_conflict", "Accounting key was already used.")
            return Success(self._receipt(prior, wallet, True, source_type, source_reference))
        wallet = await WalletRepository(session).get_for_update_by_user_id(user_id)
        if wallet is None:
            wallet = WalletORM(
                user_id=user_id,
                currency=normalized_currency,
                balance=Decimal("0"),
                is_frozen=False,
            )
            session.add(wallet)
            await session.flush()
        if wallet.currency.upper() != normalized_currency:
            return Failure("currency_mismatch", "Wallet currency does not match.")
        if wallet.is_frozen:
            return Failure("wallet_frozen", "Wallet is frozen.")
        await session.execute(
            update(WalletORM)
            .where(
                WalletORM.id == wallet.id,
                WalletORM.currency == normalized_currency,
                WalletORM.is_frozen.is_(False),
            )
            .values(balance=WalletORM.balance + value)
        )
        ledger = TransactionORM(
            wallet_id=wallet.id,
            amount=value,
            currency=normalized_currency,
            type=transaction_type,
            reference=f"{source_type}:{source_reference}",
            provider=source_type,
            provider_reference=source_reference,
            idempotency_key=idempotency_key,
            note=note,
        )
        session.add(ledger)
        await session.flush()
        fresh_wallet = await session.get(WalletORM, wallet.id)
        if fresh_wallet is None:
            return Failure("wallet_not_found", "Wallet not found.")
        return Success(self._receipt(ledger, fresh_wallet, False, source_type, source_reference))

    async def debit(
        self,
        *,
        user_id: int,
        amount: Decimal | int | str,
        currency: str,
        source_type: str,
        source_reference: str,
        idempotency_key: str,
        transaction_type: str = TransactionORM.TYPE_PURCHASE,
        order_id: int | None = None,
        note: str | None = None,
    ) -> Result[AccountingReceipt]:
        return await self._apply(
            user_id=user_id,
            amount=amount,
            currency=currency,
            direction="debit",
            transaction_type=transaction_type,
            source_type=source_type,
            source_reference=source_reference,
            idempotency_key=idempotency_key,
            order_id=order_id,
            note=note,
        )

    async def debit_in_session(  # noqa: PLR0911
        self,
        session: Any,
        *,
        user_id: int,
        amount: Decimal | int | str,
        currency: str,
        source_type: str,
        source_reference: str,
        idempotency_key: str,
        order_id: int | None = None,
        note: str | None = None,
    ) -> Result[AccountingReceipt]:
        """Debit using a caller-owned transaction/session."""
        validated = self._validate(amount, currency, source_type, source_reference, idempotency_key)
        if validated.is_failure:
            return validated
        value, normalized_currency = validated.unwrap()
        prior = (
            await session.execute(
                select(TransactionORM).where(TransactionORM.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if prior is not None:
            wallet = await session.get(WalletORM, prior.wallet_id)
            if wallet is None or wallet.user_id != user_id:
                return Failure("idempotency_conflict", "Accounting key was already used.")
            return Success(self._receipt(prior, wallet, True, source_type, source_reference))
        wallet = await WalletRepository(session).get_for_update_by_user_id(user_id)
        if wallet is None:
            return Failure("wallet_not_found", "Wallet not found.")
        if wallet.currency.upper() != normalized_currency:
            return Failure("currency_mismatch", "Wallet currency does not match.")
        if wallet.is_frozen:
            return Failure("wallet_frozen", "Wallet is frozen.")
        updated = await session.execute(
            update(WalletORM)
            .where(
                and_(
                    WalletORM.id == wallet.id,
                    WalletORM.currency == normalized_currency,
                    WalletORM.is_frozen.is_(False),
                    WalletORM.balance >= value,
                )
            )
            .values(balance=WalletORM.balance - value)
        )
        if updated.rowcount != 1:
            return Failure("insufficient_balance", "Insufficient wallet balance.")
        ledger = TransactionORM(
            wallet_id=wallet.id,
            order_id=order_id,
            amount=-value,
            currency=normalized_currency,
            type=TransactionORM.TYPE_PURCHASE,
            reference=f"{source_type}:{source_reference}",
            provider=source_type,
            provider_reference=source_reference,
            idempotency_key=idempotency_key,
            note=note,
        )
        session.add(ledger)
        await session.flush()
        fresh_wallet = await session.get(WalletORM, wallet.id)
        if fresh_wallet is None:
            return Failure("wallet_not_found", "Wallet not found.")
        return Success(self._receipt(ledger, fresh_wallet, False, source_type, source_reference))

    async def _apply(  # noqa: PLR0911, PLR0912
        self,
        *,
        user_id: int,
        amount: Decimal | int | str,
        currency: str,
        direction: str,
        transaction_type: str,
        source_type: str,
        source_reference: str,
        idempotency_key: str,
        order_id: int | None = None,
        note: str | None = None,
    ) -> Result[AccountingReceipt]:
        validated = self._validate(amount, currency, source_type, source_reference, idempotency_key)
        if validated.is_failure:
            return validated
        value, normalized_currency = validated.unwrap()
        async with self.db.session() as session:
            existing = await session.execute(
                select(TransactionORM).where(TransactionORM.idempotency_key == idempotency_key)
            )
            prior = existing.scalar_one_or_none()
            if prior is not None:
                if prior.wallet_id is None or prior.currency != normalized_currency:
                    return Failure("idempotency_conflict", "Accounting key was already used.")
                wallet = await session.get(WalletORM, prior.wallet_id)
                if wallet is None or wallet.user_id != user_id:
                    return Failure("idempotency_conflict", "Accounting key was already used.")
                return Success(self._receipt(prior, wallet, True, source_type, source_reference))

            wallet = await WalletRepository(session).get_for_update_by_user_id(user_id)
            if wallet is None:
                if direction != "credit":
                    return Failure("wallet_not_found", "Wallet not found.")
                wallet = WalletORM(
                    user_id=user_id,
                    currency=normalized_currency,
                    balance=Decimal("0"),
                    is_frozen=False,
                )
                session.add(wallet)
                await session.flush()
            if wallet.currency.upper() != normalized_currency:
                return Failure("currency_mismatch", "Wallet currency does not match.")
            if wallet.is_frozen:
                return Failure("wallet_frozen", "Wallet is frozen.")

            signed_amount = value if direction == "credit" else -value
            if direction == "debit":
                updated = await session.execute(
                    update(WalletORM)
                    .where(
                        and_(
                            WalletORM.id == wallet.id,
                            WalletORM.currency == normalized_currency,
                            WalletORM.is_frozen.is_(False),
                            WalletORM.balance >= value,
                        )
                    )
                    .values(balance=WalletORM.balance - value)
                )
                if updated.rowcount != 1:
                    return Failure("insufficient_balance", "Insufficient wallet balance.")
            else:
                await session.execute(
                    update(WalletORM)
                    .where(
                        WalletORM.id == wallet.id,
                        WalletORM.currency == normalized_currency,
                        WalletORM.is_frozen.is_(False),
                    )
                    .values(balance=WalletORM.balance + value)
                )

            ledger = TransactionORM(
                wallet_id=wallet.id,
                order_id=order_id,
                amount=signed_amount,
                currency=normalized_currency,
                type=transaction_type,
                reference=f"{source_type}:{source_reference}",
                provider=source_type,
                provider_reference=source_reference,
                idempotency_key=idempotency_key,
                note=note,
            )
            session.add(ledger)
            try:
                await session.flush()
            except IntegrityError:
                return Failure(
                    "accounting_conflict",
                    "Accounting operation conflicted; retry safely.",
                )
            fresh_wallet = await session.get(WalletORM, wallet.id)
            if fresh_wallet is None:
                return Failure("wallet_not_found", "Wallet not found.")
            return Success(
                self._receipt(ledger, fresh_wallet, False, source_type, source_reference)
            )

    @staticmethod
    def _validate(
        amount: Decimal | int | str,
        currency: str,
        source_type: str,
        source_reference: str,
        idempotency_key: str,
    ) -> Result[tuple[Decimal, str]]:
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            return Failure("invalid_amount", "Amount must be a finite positive Decimal.")
        normalized_currency = str(currency).strip().upper()
        if not value.is_finite() or value <= 0:
            return Failure("invalid_amount", "Amount must be a finite positive Decimal.")
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            return Failure("invalid_currency", "Currency must be a three-letter code.")
        if not source_type.strip() or not source_reference.strip() or not idempotency_key.strip():
            return Failure("invalid_source", "Source and idempotency references are required.")
        if len(source_reference) > 256 or len(idempotency_key) > 128:
            return Failure("invalid_source", "Source or idempotency reference is too long.")
        return Success((value, normalized_currency))

    @staticmethod
    def _receipt(
        transaction: TransactionORM,
        wallet: WalletORM,
        idempotent: bool,
        source_type: str,
        source_reference: str,
    ) -> AccountingReceipt:
        return AccountingReceipt(
            wallet_id=wallet.id,
            user_id=wallet.user_id,
            transaction_id=transaction.id,
            amount=abs(Decimal(str(transaction.amount))),
            currency=transaction.currency,
            direction="credit" if Decimal(str(transaction.amount)) > 0 else "debit",
            source_type=source_type,
            source_reference=source_reference,
            idempotent=idempotent,
        )
