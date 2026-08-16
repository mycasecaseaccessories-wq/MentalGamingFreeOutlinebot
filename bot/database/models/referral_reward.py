"""Phase 6.2 referral reward ledger.

Each beneficiary reward is an independent row.  The deterministic idempotency
key and unique constraint are the final database guard against double grants.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ReferralRewardORM(BaseModel):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_referral_rewards_idempotency"),
        UniqueConstraint("referral_id", "beneficiary_type", "reward_cycle", name="uq_referral_reward_cycle_beneficiary"),
    )

    STATUS_PENDING = "pending"
    STATUS_REVIEW_REQUIRED = "review_required"
    STATUS_LIMIT_REACHED = "limit_reached"
    STATUS_GRANTING = "granting"
    STATUS_GRANTED = "granted"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    BENEFICIARY_REFERRER = "referrer"
    BENEFICIARY_REFERRED_USER = "referred_user"

    TYPE_EXTRA_TRIAL = "extra_trial"
    TYPE_WALLET_CREDIT = "wallet_credit"
    TYPE_BONUS_DATA = "bonus_data"
    TYPE_BONUS_DURATION = "bonus_duration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_reward_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id", ondelete="RESTRICT"), nullable=False, index=True)
    beneficiary_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    beneficiary_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reward_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reward_cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=STATUS_PENDING, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    limit_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wallet_transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    entitlement_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReferralRiskEventORM(BaseModel):
    """Durable, privacy-respecting velocity event for referral anti-abuse."""
    __tablename__ = "referral_risk_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_referral_risk_event_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referral_id: Mapped[int | None] = mapped_column(ForeignKey("referrals.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    risk_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
