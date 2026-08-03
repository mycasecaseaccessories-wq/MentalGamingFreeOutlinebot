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

    Phase 0.2: table schema created; populated by SettingsService.seed_defaults().
    Phase 0.3: category column added for grouped admin panel display.
    Phase 2:   SettingsService wraps get/set with in-memory caching.
               Admin panel calls set() to update runtime configuration.

    Columns
    -------
    key          Unique setting identifier (snake_case).
    value        Stored value as a string — cast using the type column.
    type         Value type hint: str | int | float | bool | json | list.
    category     Admin panel category slug (e.g. 'general', 'vpn').
    description  Human-readable label shown in the admin settings panel.
    is_public    True if non-admin code may read this setting.
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
        comment="Value type hint: str | int | float | bool | json | list",
    )
    category: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        default="general",
        comment="Admin panel category slug — see SettingCategory in config.defaults",
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
