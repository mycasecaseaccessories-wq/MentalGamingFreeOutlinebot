"""
UserORM — the core user account table.

Each row represents one Telegram user who has interacted with the bot.
Users are identified by their immutable Telegram user ID.

Related tables (added in later phases):
  wallets      — 1:1 wallet linked via user_id FK
  vpn_keys     — 1:N keys owned by this user
  orders       — 1:N purchase orders
  referrals    — referral relationships (referrer and referred)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class UserORM(BaseModel):
    """
    Persisted user account.

    Phase 0.2: base schema — telegram_id, username, full_name, role, language,
               is_active, is_verified, referred_by.
    Phase 0.4: added first_name, last_name, status, last_active.
    Phase 1:   wire up relationships, add WalletORM FK.
    """

    __tablename__ = "users"

    # ── Telegram identity ─────────────────────────────────────────────────
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
        comment="Unique Telegram user ID (immutable)",
    )
    username: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Telegram @username — may be None or change over time",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name from the Telegram client",
    )
    first_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="First name from Telegram (Phase 0.4+)",
    )
    last_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Last name from Telegram (optional)",
    )

    # ── Platform identity ─────────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="customer",
        comment="UserRole value: admin | customer | reseller | affiliate | moderator | vip",
    )
    language: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="en",
        comment="Preferred UI language code: en | my",
    )

    # ── Account status ────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        comment="UserStatus: active | inactive | suspended | banned | pending",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Legacy flag — kept for backward compat; use status instead",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True after identity verification (Phase 3+)",
    )

    # ── Activity ──────────────────────────────────────────────────────────
    last_active: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of the user's last interaction with the bot",
    )

    # ── Referral ──────────────────────────────────────────────────────────
    referred_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="telegram_id of the user who referred this account (Phase 5)",
    )
