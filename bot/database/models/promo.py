from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class PromoCodeORM(BaseModel):
    __tablename__ = "promo_codes"
    __table_args__ = (
        UniqueConstraint("code_normalized", name="uq_promo_codes_code_normalized"),
    )

    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_EXPIRED = "expired"
    STATUS_EXHAUSTED = "exhausted"
    STATUS_DISABLED = "disabled"
    STATUS_ARCHIVED = "archived"

    TYPE_REWARD = "reward"
    TYPE_DISCOUNT = "discount"
    TYPE_CAMPAIGN = "campaign"

    REWARD_EXTRA_TRIAL = "extra_free_trial"
    REWARD_WALLET_CREDIT = "wallet_credit"
    REWARD_BONUS_DATA = "bonus_data"
    REWARD_BONUS_DURATION = "bonus_duration"
    REWARD_PERCENT_DISCOUNT = "percent_discount"
    REWARD_FIXED_DISCOUNT = "fixed_discount"
    REWARD_NONE = "none"

    ELIGIBILITY_ALL_ACTIVE = "all_active_users"
    ELIGIBILITY_NEW_USERS = "new_users_only"
    ELIGIBILITY_EXISTING_USERS = "existing_users"
    ELIGIBILITY_PAID_USERS = "paid_users_only"
    ELIGIBILITY_NEVER_PURCHASED = "never_purchased"
    ELIGIBILITY_FIRST_PURCHASE = "first_purchase_only"
    ELIGIBILITY_SPECIFIC_ROLE = "specific_role"
    ELIGIBILITY_REFERRAL_USERS = "referral_users"
    ELIGIBILITY_MISSION_COMPLETERS = "mission_completers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_promo_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    code_normalized: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    promo_type: Mapped[str] = mapped_column(String(32), nullable=False, default=TYPE_REWARD)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=STATUS_DRAFT, index=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default=REWARD_NONE)
    reward_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reward_expiry_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_redemptions_per_user: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reserved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_purchase_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    eligibility_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reward_policy_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)


class PromoRedemptionORM(BaseModel):
    __tablename__ = "promo_redemptions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_promo_redemptions_idempotency_key"),
        UniqueConstraint("promo_id", "user_id", "reservation_key", name="uq_promo_redemptions_user_reservation"),
    )

    STATUS_PENDING = "pending"
    STATUS_VALIDATING = "validating"
    STATUS_RESERVED = "reserved"
    STATUS_GRANTING = "granting"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_RETRYING = "retrying"
    STATUS_CANCELLED = "cancelled"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_redemption_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    promo_id: Mapped[int] = mapped_column(Integer, ForeignKey("promo_codes.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=STATUS_PENDING, index=True)
    reward_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    reservation_key: Mapped[str] = mapped_column(String(96), nullable=False, default="immediate")
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    eligibility_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
