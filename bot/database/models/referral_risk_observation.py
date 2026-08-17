"""Phase 6.5 privacy-safe referral risk observations and review cases."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ReferralRiskObservationORM(BaseModel):
    __tablename__ = "referral_risk_observations"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_referral_risk_observation_dedupe"),
    )

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_HELD = "held"
    STATUS_BLOCKED = "blocked"

    LEVEL_LOW = "low"
    LEVEL_MEDIUM = "medium"
    LEVEL_HIGH = "high"
    LEVEL_CRITICAL = "critical"

    ACTION_ALLOW = "allow"
    ACTION_OBSERVE = "observe"
    ACTION_REVIEW_REQUIRED = "review_required"
    ACTION_HOLD_REWARD = "hold_reward"
    ACTION_REFERRAL_REWARD_BLOCK = "referral_reward_block"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_observation_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id", ondelete="SET NULL"), nullable=True, index=True)
    reward_id: Mapped[int | None] = mapped_column(ForeignKey("referral_rewards.id", ondelete="SET NULL"), nullable=True, index=True)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default=LEVEL_LOW, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default=ACTION_OBSERVE, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_OPEN, index=True)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
