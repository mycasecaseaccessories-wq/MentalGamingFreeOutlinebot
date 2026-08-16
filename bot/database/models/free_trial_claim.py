from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class FreeTrialClaimORM(BaseModel):
    __tablename__ = "free_trial_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "period_start", "source", name="uq_free_trial_claim_period_source"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="RESTRICT"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True)
    entitlement_id: Mapped[int | None] = mapped_column(ForeignKey("free_trial_entitlements.id", ondelete="RESTRICT"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="daily_free")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="accepted")
    data_limit_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    device_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(96), nullable=True)
