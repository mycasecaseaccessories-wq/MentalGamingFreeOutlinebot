"""
ServerORM — Outline VPN server registry.

Each row represents one Outline server that the platform manages.
The platform issues VPN keys from these servers.

Columns
-------
name          Human-readable label (e.g. "Singapore #1").
api_url       Outline management API base URL (from shadowbox config).
cert_sha256   TLS certificate fingerprint for the management API.
region        Geographic region label (e.g. "Southeast Asia").
country_code  ISO 3166-1 alpha-2 code of the server location.
is_active     False prevents new keys from being issued on this server.
max_keys      Maximum number of active keys allowed. NULL = unlimited.
notes         Admin-only notes (e.g. provider, contract expiry date).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ServerORM(BaseModel):
    """
    Outline VPN server instance.

    Phase 0.2: schema placeholder.
    Phase 4:   used by ServerService to provision and rotate keys.
    """

    __tablename__ = "servers"

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Human-readable server label shown in the admin panel",
    )
    api_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        comment="Outline management API base URL",
    )
    cert_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 fingerprint of the server TLS certificate",
    )
    region: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Geographic region label for display",
    )
    country_code: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        comment="ISO 3166-1 alpha-2 country code",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False prevents new key issuance on this server",
    )
    max_keys: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Hard cap on active keys. NULL = no limit",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin-only notes — provider details, contract dates, etc.",
    )
