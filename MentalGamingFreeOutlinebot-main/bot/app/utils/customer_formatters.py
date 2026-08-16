"""Presentation-safe formatters used by Phase 1.3 customer pages."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from html import escape


def format_username(username: str | None, not_set: str) -> str:
    value = (username or "").strip().lstrip("@")
    return f"@{escape(value)}" if value else not_set


def format_optional(value: str | None, not_set: str) -> str:
    value = (value or "").strip()
    return escape(value) if value else not_set


def format_datetime(value: datetime | None, not_set: str) -> str:
    if value is None:
        return not_set
    return value.strftime("%Y-%m-%d %H:%M")


def format_money(amount: Decimal | int | str, currency: str) -> str:
    value = Decimal(str(amount))
    if value == value.to_integral_value():
        number = f"{int(value):,}"
    else:
        number = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{number} {escape(currency.upper())}"


def format_boolean(value: bool, enabled: str, disabled: str) -> str:
    return enabled if value else disabled


def format_enum(value: str) -> str:
    return escape(value.replace("_", " ").title())
