"""Phase 6.3 mission definitions, user progress, and source-event ledger."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class MissionORM(BaseModel):
    __tablename__ = "missions"
    __table_args__ = (
        UniqueConstraint("public_mission_id", name="uq_missions_public_id"),
        UniqueConstraint("public_mission_id", "policy_revision", name="uq_mission_public_revision"),
    )

    TYPE_JOIN_CHANNEL = "join_channel"
    TYPE_QUALIFIED_REFERRAL_COUNT = "qualified_referral_count"
    TYPE_FREE_TRIAL_ACTIVATED = "free_trial_activated"
    TYPE_FIRST_PAID_PURCHASE = "first_paid_purchase"
    TYPE_PAID_PURCHASE_COUNT = "paid_purchase_count"
    TYPE_PURCHASE_AMOUNT = "purchase_amount"
    TYPE_VPN_RENEWAL = "vpn_renewal"
    TYPE_DAILY_CHECK_IN = "daily_check_in"
    TYPE_WALLET_USAGE = "wallet_usage"
    TYPE_CUSTOM_EVENT = "custom_event"

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_DISABLED = "disabled"
    STATUS_ENDED = "ended"
    STATUS_ARCHIVED = "archived"

    REPEAT_ONE_TIME = "one_time"
    REPEAT_DAILY = "daily"
    REPEAT_WEEKLY = "weekly"
    REPEAT_MONTHLY = "monthly"
    REPEAT_REPEATABLE = "repeatable"
    REPEAT_EVENT_WINDOW = "event_window"

    DELIVERY_AUTO_GRANT = "auto_grant"
    DELIVERY_MANUAL_CLAIM = "manual_claim"

    REWARD_NONE = "none"
    REWARD_EXTRA_TRIAL = "extra_trial"
    REWARD_WALLET_CREDIT = "wallet_credit"
    REWARD_BONUS_DATA = "bonus_data"
    REWARD_BONUS_DURATION = "bonus_duration"
    REWARD_PROMO_ENTITLEMENT = "promo_entitlement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_mission_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mission_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=STATUS_DRAFT, index=True)
    condition_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default=REWARD_NONE)
    reward_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    reward_expiry_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_mode: Mapped[str] = mapped_column(String(24), nullable=False, default=DELIVERY_AUTO_GRANT)
    repeat_mode: Mapped[str] = mapped_column(String(24), nullable=False, default=REPEAT_ONE_TIME)
    progress_target: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reset_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Yangon")
    eligibility_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="all_active_users")
    eligibility_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class UserMissionProgressORM(BaseModel):
    __tablename__ = "user_mission_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "mission_id", "period_key", name="uq_user_mission_progress_period"),
        UniqueConstraint("idempotency_key", name="uq_user_mission_progress_idempotency"),
    )

    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_REWARD_PENDING = "reward_pending"
    STATUS_REWARD_GRANTED = "reward_granted"
    STATUS_EXPIRED = "expired"
    STATUS_BLOCKED = "blocked"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_progress_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="RESTRICT"), nullable=False, index=True)
    period_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_value_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    mission_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_type_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    reward_value_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reward_expiry_seconds_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_mode_snapshot: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=STATUS_NOT_STARTED, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_id: Mapped[int | None] = mapped_column(ForeignKey("referral_rewards.id", ondelete="RESTRICT"), nullable=True, unique=True)
    reward_public_id: Mapped[str | None] = mapped_column(String(48), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    last_source_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)


class MissionProgressEventORM(BaseModel):
    __tablename__ = "mission_progress_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_mission_progress_event_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    progress_id: Mapped[int | None] = mapped_column(ForeignKey("user_mission_progress.id", ondelete="RESTRICT"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    period_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
