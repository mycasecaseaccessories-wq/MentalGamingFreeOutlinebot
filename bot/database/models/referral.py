"""
ReferralORM — referral relationships between users.

Tracks which user introduced another user to the platform.
Used by GrowthService to calculate and credit referral commissions.

Columns
-------
referrer_id   FK → users.id — the user who shared the referral link.
referred_id   FK → users.id — the user who registered via the referral.
status        Lifecycle state: pending → qualified → rewarded | expired.
commission    Amount credited to the referrer on qualification.
currency      ISO 4217 code of the commission amount.
qualified_at  UTC timestamp when the referral met the qualifying criteria.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ReferralORM(BaseModel):
    """
    Referral relationship record.

    Phase 0.2: schema placeholder.
    Phase 5:   GrowthService creates and qualifies referral records.

    Status values
    -------------
    pending     Referred user registered but has not yet made a purchase.
    qualified   Referred user completed a qualifying purchase.
    rewarded    Commission has been credited to the referrer's wallet.
    expired     Referral window closed without qualification.
    """

    __tablename__ = "referrals"

    STATUS_PENDING   = "pending"
    STATUS_QUALIFIED = "qualified"
    STATUS_REWARDED  = "rewarded"
    STATUS_EXPIRED   = "expired"

    referrer_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="FK → users.id — the referring user",
    )
    referred_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        comment="FK → users.id — the referred user (each user referred once)",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_PENDING,
        index=True,
        comment="Referral lifecycle state",
    )
    commission: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="Commission amount credited on qualification",
    )
    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        comment="ISO 4217 code of the commission",
    )
    qualified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of qualifying event",
    )
