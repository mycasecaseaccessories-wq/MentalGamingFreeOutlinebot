"""Fake application settings for testing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeSettings:
    """Minimal fake settings object — mirrors config.settings.Settings."""

    bot_token: str = "123456789:AAFakeTokenForTestingDoNotUseInProd"
    admin_ids: list[int] = None  # type: ignore[assignment]
    database_url: str = "sqlite+aiosqlite:///:memory:"
    environment: str = "testing"
    default_language: str = "en"
    log_level: str = "WARNING"
    session_secret: str = "test-session-secret-at-least-32-chars-long"

    def __post_init__(self) -> None:
        if self.admin_ids is None:
            self.admin_ids = [100_000_001]


def make_settings(**overrides: object) -> FakeSettings:
    return FakeSettings(**overrides)  # type: ignore[arg-type]
