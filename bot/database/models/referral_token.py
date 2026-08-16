from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class ReferralTokenORM(BaseModel):
    """Stable personal token owned by exactly one platform user."""

    __tablename__ = "referral_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_referral_token_user"),
        UniqueConstraint("token", name="uq_referral_token_value"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
