"""Fake notification domain objects for testing (Phase 3+)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class FakeNotificationType(str, Enum):
    EXPIRY_REMINDER = "expiry_reminder"
    PAYMENT_RECEIVED = "payment_received"
    KEY_CREATED = "key_created"
    BROADCAST = "broadcast"


@dataclass
class FakeNotification:
    """Fake notification message."""

    id: int = 1
    user_id: int = 999_000_001
    notification_type: FakeNotificationType = FakeNotificationType.KEY_CREATED
    title: str = "Your VPN Key is Ready"
    body: str = "Your Outline VPN key has been created. Tap to copy your access URL."
    is_read: bool = False
    sent_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def make_notification(**overrides: object) -> FakeNotification:
    return FakeNotification(**overrides)  # type: ignore[arg-type]
