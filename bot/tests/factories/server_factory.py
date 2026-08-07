"""Factory for generating realistic Server test objects."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from faker import Faker

from tests.fixtures.servers import FakeServer

_faker = Faker()
_COUNTRY_CODES = ["SG", "JP", "US", "DE", "NL", "TH", "HK"]


class ServerFactory:
    _seq: int = 0

    @classmethod
    def _next_id(cls) -> int:
        cls._seq += 1
        return cls._seq

    @classmethod
    def build(cls, **overrides: Any) -> FakeServer:
        sid = cls._next_id()
        cc = random.choice(_COUNTRY_CODES)
        defaults: dict[str, Any] = {
            "id": sid,
            "name": f"{cc}-{sid:02d}",
            "api_url": f"https://192.0.{sid}.1:8080/api-{_faker.sha1()[:16]}",
            "country_code": cc,
            "is_active": True,
            "max_keys": 500,
            "current_keys": random.randint(0, 400),
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return FakeServer(**defaults)

    @classmethod
    def build_full(cls, **overrides: Any) -> FakeServer:
        return cls.build(current_keys=500, **overrides)

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[FakeServer]:
        return [cls.build(**overrides) for _ in range(count)]
