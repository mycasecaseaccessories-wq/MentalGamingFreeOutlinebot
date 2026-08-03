"""
VPNKeyORM — Outline access keys issued to users.

Each row represents one Outline access key linked to a user and a server.
The access_url contains the ss:// link the user installs in their Outline client.

Columns
-------
user_id         FK → users.id — the subscriber who owns this key.
server_id       FK → servers.id — the Outline server that hosts the key.
outline_key_id  The numeric ID returned by the Outline API (server-scoped).
access_url      The ss:// connection URL — sensitive, shared with the user.
name            Display name set on the Outline server (e.g. "Alice — Jul 2026").
data_limit_bytes Per-key data cap in bytes enforced by the Outline server.
is_active       False when the key has been revoked or expired.
expires_at      UTC timestamp when the key should be automatically revoked.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class VPNKeyORM(BaseModel):
    """
    Issued Outline VPN access key.

    Phase 0.2: schema placeholder.
    Phase 4:   provisioned via VPNService using the Outline Management API.
    """

    __tablename__ = "vpn_keys"

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="FK → users.id (enforced in Phase 4)",
    )
    server_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="FK → servers.id (enforced in Phase 4)",
    )
    outline_key_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Numeric key ID returned by the Outline Management API",
    )
    access_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="ss:// connection URL — share only with the key owner",
    )
    name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Key label on the Outline server",
    )
    data_limit_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Per-key data cap enforced by Outline. NULL = unlimited",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False after revocation or expiry",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC expiry timestamp — scheduler auto-revokes after this",
    )
