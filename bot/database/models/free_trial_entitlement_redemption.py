from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class FreeTrialEntitlementRedemptionORM(BaseModel):
    """One durable, idempotent consumption of a growth entitlement."""

    __tablename__ = "free_trial_entitlement_redemptions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_entitlement_redemption_idempotency"),
    )

    entitlement_id: Mapped[int] = mapped_column(ForeignKey("free_trial_entitlements.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="redeemed")
