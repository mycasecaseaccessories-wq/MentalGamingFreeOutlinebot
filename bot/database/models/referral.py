"""Authoritative referral attribution relationship model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ReferralORM(BaseModel):
    """One immutable primary referrer relationship for a referred user."""

    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_id", name="uq_referrals_referred_user"),
    )

    STATUS_ATTRIBUTED = "attributed"
    STATUS_PENDING_QUALIFICATION = "pending_qualification"
    STATUS_QUALIFIED = "qualified"
    STATUS_REWARDED = "rewarded"
    STATUS_INVALID = "invalid"
    STATUS_CANCELLED = "cancelled"

    SOURCE_PERSONAL_LINK = "personal_link"
    SOURCE_CAMPAIGN = "campaign"
    SOURCE_ADMIN = "admin"
    SOURCE_PROMOTION = "promotion"

    INVALID_SELF_REFERRAL = "self_referral"
    INVALID_DUPLICATE_ATTRIBUTION = "duplicate_attribution"
    INVALID_ABUSE = "abuse"
    INVALID_SOURCE = "invalid_source"
    INVALID_ADMIN = "admin_invalidated"
    INVALID_OTHER = "other"

    public_referral_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("referral_tokens.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_PENDING_QUALIFICATION, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=SOURCE_PERSONAL_LINK, index=True)
    safe_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Backward-compatible Phase 5 commission fields. Phase 6.1 does not mutate them.
    commission: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
