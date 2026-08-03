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

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class UserORM(BaseModel):
    """
    Persisted user account.

    Phase 0.2: schema placeholder — all columns defined, no FKs yet.
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

    # ── Platform identity ─────────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="customer",
        comment="UserRole enum value: admin | customer | reseller | affiliate",
    )
    language: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="en",
        comment="Preferred UI language code: en | my",
    )

    # ── Status flags ──────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False when the account is suspended",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True after identity verification (Phase 3+)",
    )

    # ── Referral ──────────────────────────────────────────────────────────
    referred_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="telegram_id of the user who referred this account (Phase 5)",
    )
