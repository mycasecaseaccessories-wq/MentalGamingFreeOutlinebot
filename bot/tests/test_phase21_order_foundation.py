"""Focused Phase 2.1 domain tests that do not require a live database."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.package_catalog import PackageSelection
from app.services.checkout_service import CheckoutService
from app.services.order_service import (
    CheckoutExpiredError,
    InvalidOrderStateError,
    OrderService,
)


def _selection(*, expires_at: datetime | None = None) -> PackageSelection:
    now = datetime.now(timezone.utc)
    return PackageSelection(
        user_id=991,
        package_id=7,
        package_name="Premium",
        package_type="paid",
        quoted_price=Decimal("8000.00"),
        currency="MMK",
        data_limit_gb=Decimal("20"),
        duration_days=30,
        device_limit=3,
        server_policy="auto",
        country=None,
        selected_at=now,
        expires_at=expires_at or now + timedelta(minutes=15),
        checkout_token="checkout-test-token",
    )


def test_public_order_ids_are_customer_safe_and_non_sequential() -> None:
    ids = {OrderService.generate_public_order_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(value.startswith("ORD-") for value in ids)


def test_order_state_machine_allows_waiting_payment_to_cancel() -> None:
    OrderService.validate_transition("waiting_payment", "cancelled")


def test_order_state_machine_rejects_paid_to_cancel() -> None:
    with pytest.raises(InvalidOrderStateError):
        OrderService.validate_transition("paid", "cancelled")


def test_checkout_session_rejects_expired_selection() -> None:
    service = CheckoutService.__new__(CheckoutService)
    expired = _selection(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(CheckoutExpiredError):
        service.get_checkout_session(expired, 991)


def test_checkout_session_rejects_wrong_customer() -> None:
    service = CheckoutService.__new__(CheckoutService)
    with pytest.raises(CheckoutExpiredError):
        service.get_checkout_session(_selection(), 992)


def test_snapshot_builder_copies_package_attributes() -> None:
    package = SimpleNamespace(
        id=7,
        name="Premium",
        package_type="paid",
        price=Decimal("8000"),
        currency="mmk",
        data_limit_gb=Decimal("20"),
        duration_days=30,
        max_devices=3,
        server_policy="auto",
        country=None,
    )
    snapshot = OrderService.build_order_snapshot(package)
    assert snapshot.package_id == 7
    assert snapshot.price == Decimal("8000")
    assert snapshot.currency == "MMK"
    assert snapshot.data_limit_gb == Decimal("20")
    assert snapshot.duration_days == 30
    assert snapshot.device_limit == 3
