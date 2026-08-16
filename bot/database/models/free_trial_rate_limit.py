from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class FreeTrialRateLimitORM(BaseModel):
    """Durable per-user/action velocity bucket shared by all workers."""

    __tablename__ = "free_trial_rate_limits"
    __table_args__ = (
        UniqueConstraint("user_id", "action", name="uq_free_trial_rate_limit_user_action"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
