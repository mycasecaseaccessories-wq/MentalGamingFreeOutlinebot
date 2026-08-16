"""
PackageORM — VPN subscription package catalogue.

Packages define what a customer can purchase: duration, data limit, and price.
The admin can create, update, and deactivate packages without code changes.

Columns
-------
name          Display name shown to users (e.g. "1 Month Premium").
description   Optional marketing copy shown in the package selection menu.
price         Price in platform currency units (e.g. MMK, USD).
currency      ISO 4217 currency code of the price column.
duration_days How many days the subscription remains active after purchase.
data_limit_gb Monthly data cap in gigabytes. NULL = unlimited.
max_devices   Number of simultaneous device connections allowed. NULL = unlimited.
is_active     False hides the package from the user-facing catalogue.
sort_order    Controls display order (ascending). Lower = shown first.
"""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class PackageORM(BaseModel):
    """
    VPN subscription package.

    Phase 0.2: schema placeholder.
    Phase 2:   populate via admin panel, link to OrderORM.
    """

    __tablename__ = "packages"


    package_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="paid",
        comment="PackageType value: paid | free_trial | promotion | reward | vip",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        comment="PackageStatus value: draft | active | hidden | disabled | archived",
    )
    visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the package is visible in customer catalogues",
    )
    renewable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether customers may renew this package later",
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="normal",
        comment="Customer-facing package priority tier",
    )
    server_policy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="auto",
        comment="auto | country | server | premium",
    )
    server_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Optional preferred server id; never exposed to customers",
    )
    country: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="Optional country code/name for customer-friendly routing policy",
    )
    badge: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Optional short customer-facing badge",
    )
    promo_label: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Optional short promotion label",
    )

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Package display name shown to users",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional marketing copy for the package",
    )
    price: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Price in the specified currency",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="ISO 4217 currency code",
    )
    duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Subscription active period in days",
    )
    data_limit_gb: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Monthly data cap in GB. NULL = unlimited",
    )
    max_devices: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Max simultaneous connections. NULL = unlimited",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False removes this package from the user-facing catalogue",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order — ascending, lower = shown first",
    )
