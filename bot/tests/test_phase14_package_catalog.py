"""Phase 1.4 package catalogue tests."""

from decimal import Decimal

from app.handlers.package_catalog import _format_decimal, _money


def test_money_format_mmk() -> None:
    assert _money(Decimal("3000"), "MMK") == "3,000 MMK"


def test_decimal_format_whole_gb() -> None:
    assert _format_decimal(Decimal("10.00")) == "10"


def test_decimal_format_fractional_gb() -> None:
    assert _format_decimal(Decimal("1.50")) == "1.5"


def test_unlimited_decimal() -> None:
    assert _format_decimal(None) == "—"
