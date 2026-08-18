from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class CallbackRateLimitORM(BaseModel):
    """Durable fixed-window counter for callback abuse control."""

    __tablename__ = "callback_rate_limits"
    __table_args__ = (UniqueConstraint("scope_key", name="uq_callback_rate_limit_scope"),)

    scope_key: Mapped[str] = mapped_column(String(192), nullable=False, index=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CallbackActionORM(BaseModel):
    """Server-side state for a sensitive Telegram callback action."""

    __tablename__ = "callback_actions"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_callback_action_public_id"),
        UniqueConstraint("token_digest", name="uq_callback_action_token_digest"),
    )

    public_id: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    chat_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_public_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    state_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
