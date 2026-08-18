"""Phase 2.2 wallet payment with atomicity and idempotency guarantees."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from decimal import Decimal

from app.core.result import Failure, Result, Success
from app.events import EventType, bus
from app.models.wallet_payment import WalletPaymentPreview, WalletPaymentReceipt
from database.models.audit_log import AuditLogORM
from database.models.order import OrderORM
from database.models.transaction import TransactionORM
from database.models.wallet import WalletORM
from sqlalchemy.exc import OperationalError
from database.repositories.order_repository import OrderRepository
from database.repositories.transaction_repository import TransactionRepository
from database.repositories.user_repository import UserRepository
from database.repositories.wallet_repository import WalletRepository
from .base import BaseService
from .maintenance_service import MaintenanceBlockedError, MaintenanceService


class WalletPaymentService(BaseService):
    """Pay an existing order from the owner's wallet in one DB transaction.

    The service deliberately does not call payment gateways, top-up providers,
    VPN providers, Outline APIs, key creation, or server-selection code.
    """

    def __init__(self, db=None, *, maintenance_service: MaintenanceService | None = None) -> None:
        super().__init__(db)
        self.maintenance_service = maintenance_service

    async def preview(
        self,
        *,
        user_id: int,
        public_order_id: str,
    ) -> Result[WalletPaymentPreview]:
        """Build a read-only confirmation preview without changing state."""
        async with self.db.session() as session:
            order_repo = OrderRepository(session)
            order = await order_repo.get_by_public_order_id(public_order_id)
            if order is None or order.user_id != user_id:
                return Failure("order_not_found", "Order not found.")
            validation = self._validate_order(order, datetime.now(timezone.utc))
            if validation is not None:
                return validation
            wallet = await WalletRepository(session).get_by_user_id(user_id)
            if wallet is None:
                return Failure("wallet_not_found", "Wallet not found.")
            if wallet.currency != order.currency:
                return Failure(
                    "currency_mismatch",
                    "This wallet cannot be used for this order currency.",
                )
            if wallet.is_frozen:
                return Failure("wallet_frozen", "This wallet is not eligible for payment.")
            amount = self._amount(order)
            balance = Decimal(str(wallet.balance))
            if balance < amount:
                return Failure(
                    "insufficient_balance",
                    "Insufficient wallet balance.",
                    details={
                        "amount": str(amount),
                        "balance": str(balance),
                        "needed": str(amount - balance),
                        "currency": order.currency,
                    },
                )
            return Success(
                WalletPaymentPreview(
                    public_order_id=order.public_order_id,
                    package_name=order.package_name_snapshot or "VPN package",
                    amount=amount,
                    currency=order.currency,
                    wallet_balance=balance,
                    balance_after=balance - amount,
                    expires_at=order.expires_at,
                )
            )

    async def pay(
        self,
        *,
        user_id: int,
        public_order_id: str,
        idempotency_key: str | None = None,
    ) -> Result[WalletPaymentReceipt]:
        """Return a safe conflict result when the database cannot acquire a lock."""
        if self.maintenance_service is not None:
            try:
                await self.maintenance_service.assert_operation_allowed("wallet_write", "SPEND")
            except MaintenanceBlockedError:
                return Failure("maintenance_active", "Wallet payments are temporarily unavailable during maintenance.")
        try:
            return await self._pay_in_transaction(
                user_id=user_id,
                public_order_id=public_order_id,
                idempotency_key=idempotency_key,
            )
        except OperationalError:
            return Failure("payment_conflict", "Payment could not be committed; please retry.")

    async def _pay_in_transaction(
        self,
        *,
        user_id: int,
        public_order_id: str,
        idempotency_key: str | None = None,
    ) -> Result[WalletPaymentReceipt]:
        """Atomically debit the wallet and mark the order paid.

        DatabaseManager.session() commits only after this entire method returns
        successfully and rolls back every mutation when any exception escapes.
        The wallet conditional UPDATE is an additional database-level guard
        against two concurrent requests spending the same balance.
        """
        payment_key = idempotency_key or f"wallet-payment:{public_order_id}"
        if len(payment_key) > 128:
            return Failure("invalid_idempotency_key", "Payment request key is too long.")

        async with self.db.session() as session:
            orders = OrderRepository(session)
            transactions = TransactionRepository(session)
            wallets = WalletRepository(session)
            now = datetime.now(timezone.utc)

            # The order lock serializes payment transitions for the same order.
            order = await orders.get_for_update_by_public_order_id(public_order_id)
            if order is None or order.user_id != user_id:
                return Failure("order_not_found", "Order not found.")

            existing = await transactions.get_by_idempotency_key(payment_key)
            if existing is not None:
                if existing.order_id != order.id or existing.wallet_id is None:
                    return Failure("idempotency_conflict", "Payment request key was already used.")
                return await self._existing_receipt(session, order, existing)

            if order.payment_status == OrderORM.PAYMENT_PAID:
                if order.wallet_transaction_id:
                    existing_tx = await session.get(TransactionORM, order.wallet_transaction_id)
                    if existing_tx is not None:
                        return await self._existing_receipt(session, order, existing_tx)
                return Failure("already_paid", "This order has already been paid.")

            validation = self._validate_order(order, now)
            if validation is not None:
                if validation.error and validation.error.code == "order_expired":
                    order.status = OrderORM.STATUS_EXPIRED
                    order.expires_at = now
                    await session.flush()
                return validation

            wallet = await wallets.get_for_update_by_user_id(user_id)
            if wallet is None:
                return Failure("wallet_not_found", "Wallet not found.")
            if wallet.currency != order.currency:
                return Failure(
                    "currency_mismatch",
                    "This wallet cannot be used for this order currency.",
                )
            if wallet.is_frozen:
                return Failure("wallet_frozen", "This wallet is not eligible for payment.")

            amount = self._amount(order)
            balance_before = Decimal(str(wallet.balance))
            if balance_before < amount:
                return Failure(
                    "insufficient_balance",
                    "Insufficient wallet balance.",
                    details={
                        "amount": str(amount),
                        "balance": str(balance_before),
                        "needed": str(amount - balance_before),
                        "currency": order.currency,
                    },
                )

            try:
                updated_wallet = await wallets.debit_if_sufficient(
                    wallet.id,
                    amount,
                    currency=order.currency,
                )
                await self._after_debit(order, wallet)
            except OperationalError:
                return Failure("payment_conflict", "Payment could not be committed; please retry.")
            if updated_wallet is None:
                return Failure("balance_changed", "Wallet balance changed; please retry.")

            payment_reference = f"wallet:{order.public_order_id}"
            ledger_row = TransactionORM(
                wallet_id=wallet.id,
                order_id=order.id,
                amount=-amount,
                currency=order.currency,
                type=TransactionORM.TYPE_PURCHASE,
                reference=payment_reference,
                idempotency_key=payment_key,
                note=f"Wallet payment for {order.public_order_id}",
            )
            session.add(ledger_row)
            await session.flush()

            order.payment_method = "wallet"
            order.payment_status = OrderORM.PAYMENT_PAID
            order.status = OrderORM.STATUS_PAID
            order.wallet_transaction_id = ledger_row.id
            order.payment_reference = payment_reference
            order.payment_ref = payment_reference
            order.paid_at = now
            await session.flush()

            session.add(
                AuditLogORM(
                    actor_id=user_id,
                    action="wallet.debited",
                    entity_type="Order",
                    entity_id=order.id,
                    new_value=json.dumps({
                        "public_order_id": order.public_order_id,
                        "wallet_id": wallet.id,
                        "transaction_id": ledger_row.id,
                        "payment_reference": payment_reference,
                        "amount": str(amount),
                        "currency": order.currency,
                        "balance_before": str(balance_before),
                        "balance_after": str(updated_wallet.balance),
                    }),
                    note=f"Wallet payment committed for {order.public_order_id}",
                )
            )
            await session.flush()

            receipt = WalletPaymentReceipt(
                public_order_id=order.public_order_id,
                transaction_id=ledger_row.id,
                payment_reference=payment_reference,
                amount=amount,
                currency=order.currency,
                remaining_balance=Decimal(str(updated_wallet.balance)),
                paid_at=now,
            )

        # DatabaseManager.session() has committed successfully at this point.
        # EventBus suppresses subscriber failures, so committed money is never
        # reversed because a notification/audit subscriber is unavailable.
        payload = {
            "user_id": user_id,
            "order_id": order.id,
            "public_order_id": receipt.public_order_id,
            "wallet_id": wallet.id,
            "transaction_id": receipt.transaction_id,
            "payment_reference": receipt.payment_reference,
            "amount": str(receipt.amount),
            "currency": receipt.currency,
            "balance_after": str(receipt.remaining_balance),
        }
        await bus.emit(EventType.WALLET_DEBITED, **payload)
        await bus.emit(EventType.ORDER_PAID, **payload)
        await bus.emit(EventType.WALLET_PAYMENT_COMPLETED, **payload)
        return Success(receipt)

    async def _after_debit(self, order: OrderORM, wallet: WalletORM) -> None:
        """Testable failure boundary before ledger/order writes; no-op in production."""
        return None

    @staticmethod
    def _amount(order: OrderORM) -> Decimal:
        amount = Decimal(str(order.total_amount))
        if amount <= 0:
            raise ValueError("Order total must be positive")
        return amount

    @staticmethod
    def _validate_order(order: OrderORM, now: datetime) -> Result[object] | None:
        if order.status in (OrderORM.STATUS_CANCELLED, OrderORM.STATUS_COMPLETED):
            return Failure("order_not_payable", "This order can no longer be paid.")
        if order.status == OrderORM.STATUS_EXPIRED:
            return Failure("order_expired", "This order has expired.")
        if order.expires_at is not None and now > order.expires_at:
            return Failure("order_expired", "This order has expired.")
        if order.payment_status in (
            OrderORM.PAYMENT_CANCELLED,
            OrderORM.PAYMENT_FAILED,
            OrderORM.PAYMENT_REFUNDED,
        ):
            return Failure("order_not_payable", "This order can no longer be paid.")
        if order.status not in (OrderORM.STATUS_PENDING, OrderORM.STATUS_WAITING_PAYMENT):
            return Failure("order_not_payable", "This order is not awaiting payment.")
        return None

    @staticmethod
    async def _existing_receipt(session, order: OrderORM, transaction: TransactionORM):
        wallet = await session.get(WalletORM, transaction.wallet_id)
        if wallet is None:
            return Failure("wallet_not_found", "Wallet not found.")
        return Success(
            WalletPaymentReceipt(
                public_order_id=order.public_order_id,
                transaction_id=transaction.id,
                payment_reference=transaction.reference or f"wallet:{order.public_order_id}",
                amount=abs(Decimal(str(transaction.amount))),
                currency=transaction.currency,
                remaining_balance=Decimal(str(wallet.balance)),
                paid_at=order.paid_at or order.updated_at,
                already_processed=True,
            )
        )
