"""Order business service for Phase 2.1.

This service creates and reads orders only. It deliberately does not mutate
wallet balances, call payment providers, or provision VPN keys.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy.exc import IntegrityError

from app.models.enums import OrderStatus, PaymentMethod
from app.models.order import Order, OrderPackageSnapshot
from app.models.package_catalog import PackageSelection
from database.models.order import OrderORM
from database.repositories.order_repository import OrderRepository
from database.repositories.package_repository import PackageRepository
from database.repositories.user_repository import UserRepository
from .base import BaseService
from .maintenance_service import MaintenanceService


class OrderNotFoundError(LookupError):
    """Raised for missing or non-owned orders without revealing their existence."""


class InvalidOrderStateError(ValueError):
    """Raised when a requested order transition is not allowed."""


class CheckoutExpiredError(ValueError):
    """Raised when a server-side checkout session is stale."""


class PackageChangedError(ValueError):
    """Raised when package attributes changed after customer selection."""


class CustomerRestrictedError(PermissionError):
    """Raised when a banned or suspended customer attempts to order."""


class OrderService(BaseService):
    """Create/read/cancel orders while keeping payment and provisioning deferred."""

    def __init__(self, db=None, maintenance_service: MaintenanceService | None = None):
        super().__init__(db)
        self.maintenance_service = maintenance_service

    _ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
        OrderORM.STATUS_PENDING: frozenset({
            OrderORM.STATUS_WAITING_PAYMENT,
            OrderORM.STATUS_CANCELLED,
            OrderORM.STATUS_EXPIRED,
        }),
        OrderORM.STATUS_WAITING_PAYMENT: frozenset({
            OrderORM.STATUS_AWAITING_APPROVAL,
            OrderORM.STATUS_PAID,
            OrderORM.STATUS_CANCELLED,
            OrderORM.STATUS_EXPIRED,
        }),
        OrderORM.STATUS_AWAITING_APPROVAL: frozenset({
            OrderORM.STATUS_WAITING_PAYMENT,
            OrderORM.STATUS_PAID,
            OrderORM.STATUS_EXPIRED,
        }),
        OrderORM.STATUS_PAID: frozenset({OrderORM.STATUS_COMPLETED, OrderORM.STATUS_REFUNDED}),
        OrderORM.STATUS_COMPLETED: frozenset(),
        OrderORM.STATUS_CANCELLED: frozenset(),
        OrderORM.STATUS_EXPIRED: frozenset(),
        OrderORM.STATUS_REFUNDED: frozenset(),
    }

    @classmethod
    def validate_transition(cls, current: str | OrderStatus, target: str | OrderStatus) -> None:
        current_value = current.value if isinstance(current, OrderStatus) else current
        target_value = target.value if isinstance(target, OrderStatus) else target
        if target_value not in cls._ALLOWED_TRANSITIONS.get(current_value, frozenset()):
            raise InvalidOrderStateError(
                f"Invalid order transition: {current_value} -> {target_value}"
            )

    @staticmethod
    def generate_public_order_id(now: datetime | None = None) -> str:
        """Return a support-friendly, non-sequential public order number."""
        stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
        return f"ORD-{stamp}-{secrets.token_hex(3).upper()}"

    @staticmethod
    def build_order_snapshot(package) -> OrderPackageSnapshot:
        return OrderPackageSnapshot(
            package_id=package.id,
            name=package.name,
            package_type=package.package_type,
            price=Decimal(str(package.price)),
            currency=(package.currency or "MMK").upper(),
            data_limit_gb=(
                None if package.data_limit_gb is None else Decimal(str(package.data_limit_gb))
            ),
            duration_days=int(package.duration_days),
            device_limit=package.max_devices,
            server_policy=package.server_policy,
            country=package.country,
        )

    @staticmethod
    def _to_domain(row: OrderORM) -> Order:
        snapshot = OrderPackageSnapshot(
            package_id=row.package_id,
            name=row.package_name_snapshot or "Unknown package",
            package_type=row.package_type_snapshot or "paid",
            price=Decimal(str(row.price_snapshot or row.total_amount or row.amount or 0)),
            currency=(row.currency or "MMK").upper(),
            data_limit_gb=(
                None
                if row.data_limit_gb_snapshot is None
                else Decimal(str(row.data_limit_gb_snapshot))
            ),
            duration_days=int(row.duration_days_snapshot or 0),
            device_limit=row.device_limit_snapshot,
            server_policy=row.server_policy_snapshot or "auto",
            country=row.country_snapshot,
        )
        method = None
        if row.payment_method:
            try:
                method = PaymentMethod(row.payment_method)
            except ValueError:
                method = None
        return Order(
            public_order_id=row.public_order_id,
            user_id=row.user_id,
            status=OrderStatus(row.status),
            payment_status=row.payment_status,
            payment_method=method,
            total_amount=Decimal(str(row.total_amount or row.amount or 0)),
            currency=(row.currency or "MMK").upper(),
            package_snapshot=snapshot,
            created_at=row.created_at,
            expires_at=row.expires_at,
            cancelled_at=row.cancelled_at,
        )

    async def create_pending_order(
        self,
        user_id: int,
        selection: PackageSelection,
        *,
        payment_timeout_minutes: int = 30,
    ) -> Order:
        """Atomically create or return the open order for a checkout token."""
        if self.maintenance_service is not None:
            await self.maintenance_service.assert_operation_allowed("orders", "CREATE")
        if selection.user_id != user_id:
            raise OrderNotFoundError("Checkout session does not belong to this customer")
        if selection.expires_at <= datetime.now(timezone.utc):
            raise CheckoutExpiredError("Checkout session has expired")

        async with self.db.session() as session:
            user = await UserRepository(session).get_by_telegram_id(user_id)
            if user is None or not user.is_active or user.status in {"banned", "suspended"}:
                raise CustomerRestrictedError("Customer cannot create an order")

            package = await PackageRepository(session).get_customer_package(selection.package_id)
            if package is None:
                raise PackageChangedError("Package is no longer available")
            current = self.build_order_snapshot(package)
            selected = OrderPackageSnapshot(
                package_id=selection.package_id,
                name=selection.package_name,
                package_type=selection.package_type,
                price=selection.quoted_price,
                currency=selection.currency,
                data_limit_gb=selection.data_limit_gb,
                duration_days=selection.duration_days,
                device_limit=selection.device_limit,
                server_policy=selection.server_policy,
                country=selection.country,
            )
            if current != selected:
                raise PackageChangedError("Package details changed; confirmation is required again")

            repo = OrderRepository(session)
            existing = await repo.find_open_order(user_id, selection.checkout_token)
            if existing is not None:
                return self._to_domain(existing)

            now = datetime.now(timezone.utc)
            values = {
                "user_id": user_id,
                "package_id": current.package_id,
                "public_order_id": self.generate_public_order_id(now),
                "checkout_token": selection.checkout_token,
                "status": OrderORM.STATUS_WAITING_PAYMENT,
                "payment_status": OrderORM.PAYMENT_UNPAID,
                "currency": current.currency,
                "subtotal_amount": current.price,
                "discount_amount": Decimal("0"),
                "total_amount": current.price,
                "amount": current.price,
                "package_name_snapshot": current.name,
                "package_type_snapshot": current.package_type,
                "data_limit_gb_snapshot": current.data_limit_gb,
                "duration_days_snapshot": current.duration_days,
                "device_limit_snapshot": current.device_limit,
                "price_snapshot": current.price,
                "server_policy_snapshot": current.server_policy,
                "country_snapshot": current.country,
                "expires_at": now + timedelta(minutes=max(1, payment_timeout_minutes)),
            }
            try:
                async with session.begin_nested():
                    row = await repo.create(**values)
            except IntegrityError:
                # A concurrent confirmation may have won the unique token race.
                existing = await repo.get_by_checkout_token(selection.checkout_token)
                if existing is None:
                    raise
                if existing.user_id != user_id:
                    raise OrderNotFoundError("Checkout session does not belong to this customer")
                return self._to_domain(existing)
            return self._to_domain(row)

    async def get_customer_order(self, user_id: int, public_order_id: str) -> Order:
        async with self.db.session() as session:
            row = await OrderRepository(session).get_by_user_id(user_id, public_order_id)
            if row is None:
                raise OrderNotFoundError("Order not found")
            return self._to_domain(row)

    async def get_order_by_public_id(self, user_id: int, public_order_id: str) -> Order:
        """Ownership-safe public lookup; never returns another customer's order."""
        return await self.get_customer_order(user_id, public_order_id)

    async def list_customer_orders(self, user_id: int, limit: int = 20) -> list[Order]:
        async with self.db.session() as session:
            rows = await OrderRepository(session).list_by_user(user_id, limit)
            return [self._to_domain(row) for row in rows]

    async def cancel_order(self, user_id: int, public_order_id: str) -> Order:
        async with self.db.session() as session:
            repo = OrderRepository(session)
            row = await repo.get_by_user_id(user_id, public_order_id)
            if row is None:
                raise OrderNotFoundError("Order not found")
            self.validate_transition(row.status, OrderORM.STATUS_CANCELLED)
            updated = await repo.mark_cancelled(
                row.id,
                datetime.now(timezone.utc),
                "Cancelled by customer before payment",
            )
            return self._to_domain(updated or row)

    async def expire_order(self, public_order_id: str) -> Order | None:
        async with self.db.session() as session:
            repo = OrderRepository(session)
            row = await repo.get_by_public_order_id(public_order_id)
            if row is None:
                return None
            self.validate_transition(row.status, OrderORM.STATUS_EXPIRED)
            updated = await repo.mark_expired(row.id, now=datetime.now(timezone.utc))
            return None if updated is None else self._to_domain(updated)

    async def expire_pending_orders(self) -> int:
        """Scheduler-compatible expiry sweep; no payment or wallet side effects."""
        now = datetime.now(timezone.utc)
        changed = 0
        async with self.db.session() as session:
            repo = OrderRepository(session)
            for row in await repo.list_expirable(now):
                self.validate_transition(row.status, OrderORM.STATUS_EXPIRED)
                await repo.mark_expired(row.id, now=now)
                changed += 1
        return changed
