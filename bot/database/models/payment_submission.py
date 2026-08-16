"""Manual payment proof submissions awaiting admin review."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class PaymentSubmissionORM(BaseModel):
    """Customer-submitted manual payment evidence; never marks an order paid."""

    __tablename__ = "payment_submissions"
    __table_args__ = (
        UniqueConstraint("public_payment_id", name="uq_payment_submissions_public_id"),
        UniqueConstraint("idempotency_key", name="uq_payment_submissions_idempotency"),
    )

    STATUS_DRAFT = "draft"
    STATUS_PENDING_REVIEW = "pending_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_payment_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    proof_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    proof_file_unique_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    proof_file_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_PENDING_REVIEW, index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True,
    )
