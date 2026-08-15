"""
UserPreferenceORM — per-user configurable preferences table.

One row per user.  All preferences are stored as typed columns so they
are queryable, indexable, and easily migrated — not as a JSON blob or
an EAV (key-value) table.

Adding a new preference field:
  1. Add a Mapped column below with a sensible default.
  2. Write an Alembic migration that adds the column (batch_alter_table).
  3. Add the corresponding field to app/models/user_preference.py (domain).
  4. Add a PreferenceKey constant in app/models/user_preference.py.
  5. Update PreferenceService.DEFAULTS dict.

Phase 0.5: Initial schema — language, timezone, notifications,
           privacy, theme, server country, currency, last_menu.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class UserPreferenceORM(BaseModel):
    """
    Persisted per-user preferences.

    Linked to the users table via telegram_id (application-level FK;
    no DB-level FOREIGN KEY constraint until Phase 1 adds SQLAlchemy
    relationships).

    Phase 0.5: foundation schema.
    Future phases: additional columns added via Alembic migrations.
    """

    __tablename__ = "user_preferences"

    # ── User link ─────────────────────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
        comment="Telegram user ID — mirrors users.telegram_id (app-level FK)",
    )

    # ── Language & region ─────────────────────────────────────────────────
    language: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="en",
        comment="Preferred UI language code: 'en' | 'my'",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Rangoon",
        comment="IANA timezone string for displaying dates/times (e.g. 'Asia/Rangoon')",
    )
    preferred_currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="MMK",
        comment="ISO 4217 currency code for pricing display (e.g. 'MMK', 'USD')",
    )

    # ── Notifications ─────────────────────────────────────────────────────
    notification_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True = user receives expiry/renewal/system notifications",
    )
    broadcast_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True = user receives admin broadcast messages",
    )

    # ── Privacy ───────────────────────────────────────────────────────────
    privacy_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=(
            "True = bot minimises data logging and hides sensitive fields "
            "in admin views.  Full enforcement in Phase 3+."
        ),
    )

    # ── UI / theme ────────────────────────────────────────────────────────
    theme: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="default",
        comment=(
            "UI theme token for the Telegram Mini App (Phase 4+). "
            "Values: 'default' | 'dark' | 'light' | 'system'."
        ),
    )
    last_menu: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "Identifier of the last menu the user visited (e.g. 'packages', "
            "'wallet').  Used to restore navigation state on /start."
        ),
    )
    language_selected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True after the user explicitly confirms a language during onboarding",
    )

    # ── Server preference ─────────────────────────────────────────────────
    preferred_server_country: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "ISO 3166-1 alpha-2 country code for preferred VPN server "
            "(e.g. 'SG', 'JP').  None = no preference; Phase 2+ enforcement."
        ),
    )
