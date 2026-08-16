"""Factory for generating realistic Notification test objects."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from faker import Faker

from tests.fixtures.notifications import FakeNotification, FakeNotificationType

_faker = Faker()


class NotificationFactory:
    _seq: int = 0

    @classmethod
    def _next_id(cls) -> int:
        cls._seq += 1
        return cls._seq

    @classmethod
    def build(cls, **overrides: Any) -> FakeNotification:
        ntype = random.choice(list(FakeNotificationType))
        defaults: dict[str, Any] = {
            "id": cls._next_id(),
            "user_id": 999_000_001,
            "notification_type": ntype,
            "title": _faker.sentence(nb_words=5),
            "body": _faker.paragraph(nb_sentences=2),
            "is_read": False,
            "sent_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return FakeNotification(**defaults)

    @classmethod
    def build_read(cls, **overrides: Any) -> FakeNotification:
        return cls.build(is_read=True, sent_at=datetime.now(timezone.utc), **overrides)

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[FakeNotification]:
        return [cls.build(**overrides) for _ in range(count)]
