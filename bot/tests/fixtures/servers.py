"""Fake Outline VPN server domain objects for testing (Phase 4+)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FakeServer:
    """Fake Outline VPN server."""

    id: int = 1
    name: str = "SG-01"
    api_url: str = "https://192.0.2.10:8080/api-secret"
    country_code: str = "SG"
    is_active: bool = True
    max_keys: int = 500
    current_keys: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def make_server(**overrides: object) -> FakeServer:
    return FakeServer(**overrides)  # type: ignore[arg-type]


def make_full_server(**overrides: object) -> FakeServer:
    """A server at full capacity."""
    return make_server(current_keys=500, **overrides)
