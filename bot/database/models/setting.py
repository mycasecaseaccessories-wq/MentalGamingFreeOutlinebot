"""
SettingORM — flexible key-value platform configuration store.

Stores runtime-adjustable platform settings without requiring a code deploy.
Admins can update settings via the admin panel (Phase 2+).

Columns
-------
key          Unique setting identifier (e.g. "force_join_enabled").
value        Stored value as a string; cast using the type column.
type         Value type hint: str | int | float | bool | json.
description  Human-readable explanation of what the setting controls.
is_public    True if this setting can be read by non-admin code paths.

Example rows
------------
key="force_join_enabled"   value="false"  type="bool"
key="free_trial_enabled"   value="true"   type="bool"
key="default_language"     value="en"     type="str"
key="exchange_rate_usd_mmk" value="2100"  type="float"
key="maintenance_mode"     value="false"  type="bool"
key="referral_commission_pct" value="10"  type="float"
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class SettingORM(BaseModel):
    """
    Runtime configuration key-value pair.

    Phase 0.2: table created with schema, populated in Phase 2 seeding.
    Phase 2:   SettingsRepository exposes typed get/set helpers.
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique setting key — use snake_case (e.g. force_join_enabled)",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Setting value stored as string — cast using the type column",
    )
    type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="str",
        comment="Value type hint: str | int | float | bool | json",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description shown in the admin settings panel",
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if non-admin code can read this setting",
    )
