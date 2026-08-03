"""
NotificationORM — scheduled or sent notification records.

Tracks every notification the platform dispatches so they can be logged,
retried on failure, and deduplicated.

Columns
-------
user_id     FK → users.id — recipient.
type        Notification category (e.g. "subscription_expiring", "key_issued").
channel     Delivery channel: telegram | email (future).
subject     Short summary / Telegram message preview.
body        Full notification body (may contain HTML).
status      Lifecycle state: queued | sent | failed | skipped.
sent_at     UTC timestamp when the notification was successfully delivered.
error       Error message if delivery failed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.base import BaseModel


class NotificationORM(BaseModel):
    """
    Outbound notification record.

    Phase 0.2: schema placeholder.
    Phase 1:   NotificationService writes records for every dispatched message.

    Status values
    -------------
    queued    Scheduled but not yet sent.
    sent      Successfully delivered.
    failed    Delivery attempted but failed (see error column).
    skipped   Deliberately not sent (e.g. user opted out).
    """

    __tablename__ = "notifications"

    STATUS_QUEUED  = "queued"
    STATUS_SENT    = "sent"
    STATUS_FAILED  = "failed"
    STATUS_SKIPPED = "skipped"

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="FK → users.id — notification recipient",
    )
    type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Notification category (e.g. subscription_expiring, key_issued)",
    )
    channel: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="telegram",
        comment="Delivery channel: telegram | email",
    )
    subject: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="Short summary or Telegram message preview",
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full notification body — may contain HTML for Telegram parse mode",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_QUEUED,
        index=True,
        comment="Delivery lifecycle state",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of successful delivery",
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error detail when status = failed",
    )
