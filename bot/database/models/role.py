"""
RoleORM — role definitions and permission descriptors.

In Phase 0 the role is stored as a plain string column on UserORM.
This table becomes the authoritative permission registry in Phase 2+
when fine-grained permission bits are introduced.

Columns
-------
name         Unique role identifier matching the UserRole enum value.
label        Human-readable display name (e.g. "Administrator").
description  What this role can do — shown in the admin panel.
is_system    True for built-in roles that cannot be deleted.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class RoleORM(BaseModel):
    """
    Platform role definition.

    Phase 0.2: schema placeholder.
    Phase 2:   link to permissions table, enforce via middleware.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        comment="Role identifier: admin | customer | reseller | affiliate",
    )
    label: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Human-readable role name shown in the admin UI",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of what this role allows",
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True for built-in roles that cannot be deleted via the UI",
    )
