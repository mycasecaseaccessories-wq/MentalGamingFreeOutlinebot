"""Fake VPN key domain objects for testing (Phase 4+)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FakeVPNKey:
    """Fake Outline VPN key."""

    id: int = 1
    user_id: int = 999_000_001
    server_id: int = 1
    outline_key_id: str = "outline-key-001"
    access_url: str = "ss://base64encoded@192.0.2.1:12345/"
    data_limit_bytes: int = 53_687_091_200  # 50 GB
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


def make_vpn_key(**overrides: object) -> FakeVPNKey:
    return FakeVPNKey(**overrides)  # type: ignore[arg-type]
