"""Factory for generating realistic VPNKey test objects."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from faker import Faker

from tests.fixtures.vpn_keys import FakeVPNKey

_faker = Faker()


class VPNFactory:
    _seq: int = 0

    @classmethod
    def _next_id(cls) -> int:
        cls._seq += 1
        return cls._seq

    @classmethod
    def _fake_access_url(cls, seq: int) -> str:
        """Generate a plausible Shadowsocks access URL (for testing only)."""
        payload = f"chacha20-ietf-poly1305:{_faker.sha256()}"
        encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        return f"ss://{encoded}@192.0.2.{seq % 254 + 1}:{10000 + seq}/"

    @classmethod
    def build(cls, **overrides: Any) -> FakeVPNKey:
        seq = cls._next_id()
        defaults: dict[str, Any] = {
            "id": seq,
            "user_id": 999_000_001,
            "server_id": 1,
            "outline_key_id": f"outline-key-{seq:04d}",
            "access_url": cls._fake_access_url(seq),
            "data_limit_bytes": 53_687_091_200,  # 50 GB
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "expires_at": None,
        }
        defaults.update(overrides)
        return FakeVPNKey(**defaults)

    @classmethod
    def build_expired(cls, **overrides: Any) -> FakeVPNKey:
        from datetime import timedelta

        past = datetime.now(timezone.utc) - timedelta(days=1)
        return cls.build(is_active=False, expires_at=past, **overrides)

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[FakeVPNKey]:
        return [cls.build(**overrides) for _ in range(count)]
