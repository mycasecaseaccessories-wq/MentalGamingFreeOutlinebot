"""
Global project constants.

All magic numbers, default values, and project-wide string identifiers
belong here.  Import from this module instead of duplicating literals.

Usage:
    from app.core.constants import BOT_VERSION, CacheTTL, Limits
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Project identity
# ---------------------------------------------------------------------------

BOT_NAME: str = "Mental VPN"
"""Display name shown in welcome messages, notifications, and the admin panel."""

BOT_VERSION: str = "0.6.1"
"""Semantic version of the current bot release."""

PROJECT_NAME: str = "Mental Outline VPN Platform"
"""Full marketing name of the platform."""

# ---------------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------------

DEFAULT_LANGUAGE: str = "en"
"""Fallback UI language code when a user has no preference set."""

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "my")
"""All language codes the platform currently supports."""

# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

DEFAULT_CURRENCY: str = "MMK"
"""ISO 4217 currency code used for price display when none is configured."""

SUPPORTED_CURRENCIES: tuple[str, ...] = ("MMK", "USD", "THB", "USDT")
"""Currencies the platform will accept or display."""

# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------

DEFAULT_TIMEZONE: str = "Asia/Yangon"
"""IANA timezone string for date/time display and scheduling."""

SUPPORTED_TIMEZONES: tuple[str, ...] = (
    "Asia/Yangon",
    "Asia/Bangkok",
    "Asia/Singapore",
    "UTC",
)
"""Timezones users may select in their preferences."""

# ---------------------------------------------------------------------------
# Cache TTLs (seconds)
# ---------------------------------------------------------------------------

class CacheTTL:
    """Centralised cache time-to-live values (in seconds)."""

    SETTINGS:     int = 300    # Platform settings  — 5 min
    USER:         int = 120    # User profile       — 2 min
    LANGUAGE:     int = 600    # Locale translations — 10 min
    SESSION:      int = 3_600  # Session data       — 1 hour
    HEALTH:       int = 30     # Health check result — 30 sec
    PACKAGE:      int = 180    # Package catalogue  — 3 min
    SERVER:       int = 60     # Server list        — 1 min
    SHORT:        int = 30     # Generic short TTL
    LONG:         int = 3_600  # Generic long TTL


# Serialisable cache policies for adapters and future API clients.
CACHE_TTL: dict[str, int] = {
    "settings": CacheTTL.SETTINGS,
    "user": CacheTTL.USER,
    "language": CacheTTL.LANGUAGE,
    "session": CacheTTL.SESSION,
    "health": CacheTTL.HEALTH,
    "package": CacheTTL.PACKAGE,
    "server": CacheTTL.SERVER,
    "short": CacheTTL.SHORT,
    "long": CacheTTL.LONG,
}


# ---------------------------------------------------------------------------
# Session / security
# ---------------------------------------------------------------------------

SESSION_TIMEOUT: int = 3_600
"""Seconds before an idle session is invalidated."""

TOKEN_EXPIRY: int = 86_400
"""Seconds before a generated token (e.g. reset link) expires (24 h)."""

MAX_RETRY: int = 3
"""Maximum automatic retries for transient failures (HTTP, DB, …)."""

MAX_FAILED_LOGINS: int = 5
"""Consecutive failures before rate-limiting kicks in."""

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE: int = 10
"""Default number of items returned per paginated query."""

MAX_PAGE_SIZE: int = 100
"""Hard cap on page size to prevent runaway queries."""

# ---------------------------------------------------------------------------
# Content limits
# ---------------------------------------------------------------------------

class Limits:
    """Input and content size limits."""

    USERNAME_MAX:     int = 64    # Telegram @username max length
    FULL_NAME_MAX:    int = 128   # User display name
    PACKAGE_NAME_MAX: int = 64    # Package title
    MESSAGE_MAX:      int = 4_096 # Telegram message character limit
    BROADCAST_MAX:    int = 4_000 # Broadcast message (leave room for footer)
    NOTE_MAX:         int = 512   # Admin notes on orders/users
    REASON_MAX:       int = 256   # Ban/suspension reason

# ---------------------------------------------------------------------------
# VPN defaults
# ---------------------------------------------------------------------------

class VPNDefaults:
    """Default values used when creating VPN keys."""

    DATA_LIMIT_GB:    float = 0.0   # 0 = unlimited
    DURATION_DAYS:    int   = 30
    FREE_TRIAL_DAYS:  int   = 3
    FREE_TRIAL_GB:    float = 1.0

# ---------------------------------------------------------------------------
# Cache tag prefixes (used by CacheService tag-based invalidation)
# ---------------------------------------------------------------------------

class CacheTag:
    """Namespace prefixes for cache tags."""

    USER:     str = "user"
    PACKAGE:  str = "package"
    SERVER:   str = "server"
    SETTINGS: str = "settings"
    SESSION:  str = "session"
    LOCALE:   str = "locale"
