from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class FreeTrialUpgradeOfferORM(BaseModel):
    __tablename__ = "free_trial_upgrade_offers"
    __table_args__ = (UniqueConstraint("public_offer_id", name="uq_free_trial_upgrade_offer_public_id"),)

    public_offer_id: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    upgrade_type: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    additional_data_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    additional_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id", ondelete="SET NULL"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_purchases_per_trial: Mapped[int | None] = mapped_column(Integer, nullable=True)


class FreeTrialUpgradeORM(BaseModel):
    __tablename__ = "free_trial_upgrades"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_free_trial_upgrade_idempotency"),
        UniqueConstraint("order_id", name="uq_free_trial_upgrade_order"),
    )

    public_upgrade_id: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    vpn_key_id: Mapped[int] = mapped_column(ForeignKey("vpn_keys.id", ondelete="RESTRICT"), nullable=False, index=True)
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("free_trial_claims.id", ondelete="SET NULL"), nullable=True, index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("free_trial_upgrade_offers.id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), nullable=False)
    upgrade_type: Mapped[str] = mapped_column(String(32), nullable=False)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_snapshot: Mapped[str] = mapped_column(String(3), nullable=False)
    data_bytes_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_package_id_snapshot: Mapped[int | None] = mapped_column(ForeignKey("packages.id", ondelete="SET NULL"), nullable=True)
    target_data_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="payment_pending", index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FreeTrialRestrictionORM(BaseModel):
    __tablename__ = "free_trial_restrictions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_free_trial_restriction_user"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
