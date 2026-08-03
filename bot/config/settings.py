"""
Centralized configuration module.

All runtime configuration is read from environment variables here.
Never hardcode secrets or environment-specific values anywhere else in the codebase.

Usage:
    from config import settings
    print(settings.bot_token)
"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """
    Application settings loaded from environment variables at startup.

    All attributes mirror the corresponding environment variable names (lowercase).
    Raises ValueError on startup if a required variable is missing.
    """

    # ── Telegram ──────────────────────────────────────────────────────────────
    bot_token: str = field(default_factory=lambda: _require("BOT_TOKEN"))
    """Telegram bot token obtained from @BotFather."""

    # ── Administration ────────────────────────────────────────────────────────
    admin_ids: List[int] = field(default_factory=lambda: _parse_int_list("ADMIN_IDS"))
    """Comma-separated list of Telegram user IDs with admin privileges."""

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = field(
        default_factory=lambda: _resolve_database_url()
    )
    """
    Async database connection string for the bot.

    Reads BOT_DATABASE_URL first (bot-specific override).
    Falls back to a local SQLite file so the bot stays independent from any
    other service that owns DATABASE_URL in the same environment.

    Sync scheme prefixes are auto-upgraded to their async equivalents:
      sqlite://         → sqlite+aiosqlite://
      postgresql://     → postgresql+asyncpg://
      postgres://       → postgresql+asyncpg://
    """

    # ── Internationalisation ──────────────────────────────────────────────────
    default_language: str = field(
        default_factory=lambda: os.getenv("DEFAULT_LANGUAGE", "en")
    )
    """
    Default language code for new users.
    Supported: 'en' (English), 'my' (Myanmar).
    """

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    """
    Logging verbosity level.
    One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """

    # ── Runtime ───────────────────────────────────────────────────────────────
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    """Runtime environment tag: 'development' | 'staging' | 'production'."""

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Return True when running in the development environment."""
        return self.environment == "development"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_database_url() -> str:
    """
    Return the async database URL for the bot.

    Priority:
      1. BOT_DATABASE_URL environment variable (explicit bot override).
      2. SQLite development default.

    The DATABASE_URL variable is intentionally ignored here — on Replit it is
    a runtime-managed key that points to the shared PostgreSQL instance used
    by other services (e.g. the Node.js API server).
    """
    raw = os.getenv("BOT_DATABASE_URL", "sqlite+aiosqlite:///./data/mental_vpn.db")
    # Auto-upgrade sync scheme prefixes to their async equivalents.
    if raw.startswith("postgresql://") or raw.startswith("postgres://"):
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw.startswith("sqlite:///") and "+aiosqlite" not in raw:
        raw = raw.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return raw


def _require(key: str) -> str:
    """Read a required environment variable; raise ValueError when absent."""
    value = os.getenv(key)
    if not value:
        raise ValueError(
            f"Required environment variable '{key}' is not set. "
            "Check your .env file or Replit Secrets."
        )
    return value


def _parse_int_list(key: str) -> List[int]:
    """
    Parse a comma-separated list of integers from an environment variable.

    Example:
        ADMIN_IDS=123456789,987654321  →  [123456789, 987654321]
    """
    raw = os.getenv(key, "")
    if not raw.strip():
        return []
    try:
        return [int(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError(
            f"Environment variable '{key}' must contain comma-separated integers. "
            f"Got: '{raw}'"
        ) from exc


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------

settings = Settings()
