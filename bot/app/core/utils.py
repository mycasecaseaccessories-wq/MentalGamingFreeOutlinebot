"""
Common shared utilities.

A collection of pure helper functions that are genuinely reusable across
all modules.  Every function here must be stateless and side-effect-free
(except environment/file helpers which are clearly labelled).

Sub-sections
------------
DateHelper      — Date/time construction, formatting, arithmetic.
TimeHelper      — Durations, countdowns, human-readable elapsed times.
Formatter       — Text, bytes, numbers, truncation.
CurrencyFormatter — Price formatting with currency symbol lookup.
RandomGenerator — Non-cryptographic random helpers.
HashHelper      — Quick convenience wrappers (see security.py for HMAC).
UUIDHelper      — UUID generation and parsing.
JSONHelper      — Safe JSON encode/decode with custom types.
FileHelper      — Path checks, size formatting, extension utilities.
StringHelper    — Slug generation, case conversion, padding.
EnvironmentHelper — Reading typed env vars with defaults.
RetryHelper     — Exponential-backoff retry for async callables.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import string
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# DateHelper
# ---------------------------------------------------------------------------

class DateHelper:
    """Utilities for date and datetime construction."""

    @staticmethod
    def now_utc() -> datetime:
        """Return the current UTC datetime (timezone-aware)."""
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def today_utc() -> date:
        """Return the current UTC date."""
        return datetime.now(tz=timezone.utc).date()

    @staticmethod
    def from_timestamp(ts: float) -> datetime:
        """Convert a Unix timestamp to a timezone-aware UTC datetime."""
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    @staticmethod
    def add_days(dt: datetime, days: int) -> datetime:
        """Return *dt* shifted forward (or backward) by *days*."""
        return dt + timedelta(days=days)

    @staticmethod
    def add_hours(dt: datetime, hours: int) -> datetime:
        """Return *dt* shifted by *hours*."""
        return dt + timedelta(hours=hours)

    @staticmethod
    def is_past(dt: datetime) -> bool:
        """Return True if *dt* is in the past relative to UTC now."""
        now = datetime.now(tz=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < now

    @staticmethod
    def days_until(dt: datetime) -> int:
        """Return the number of whole days remaining until *dt* (0 if past)."""
        now = datetime.now(tz=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - now).days
        return max(0, delta)

    @staticmethod
    def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
        """Format *dt* as a date string."""
        return dt.strftime(fmt)

    @staticmethod
    def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M UTC") -> str:
        """Format *dt* as a datetime string."""
        return dt.strftime(fmt)


# ---------------------------------------------------------------------------
# TimeHelper
# ---------------------------------------------------------------------------

class TimeHelper:
    """Utilities for durations and human-readable elapsed times."""

    @staticmethod
    def human_duration(seconds: int) -> str:
        """
        Convert *seconds* to a human-readable duration string.

        Examples:
            30      → "30 seconds"
            90      → "1 minute"
            3601    → "1 hour"
            86401   → "1 day"
        """
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        days = hours // 24
        return f"{days} day{'s' if days != 1 else ''}"

    @staticmethod
    def human_timedelta(delta: timedelta) -> str:
        """Convert a timedelta to a human-readable string."""
        return TimeHelper.human_duration(int(delta.total_seconds()))

    @staticmethod
    def countdown_label(expires_at: datetime) -> str:
        """
        Return a short expiry label such as '3 days left' or 'Expired'.

        Args:
            expires_at: Expiry datetime (UTC).
        """
        if DateHelper.is_past(expires_at):
            return "Expired"
        days = DateHelper.days_until(expires_at)
        if days == 0:
            return "Expires today"
        return f"{days} day{'s' if days != 1 else ''} left"


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class Formatter:
    """Generic text and number formatting utilities."""

    @staticmethod
    def bytes_to_human(num_bytes: float) -> str:
        """
        Convert byte count to a human-readable string.

        Example: 1_500_000_000 → "1.40 GB"
        """
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:.2f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.2f} PB"

    @staticmethod
    def truncate(text: str, max_length: int = 100, suffix: str = "…") -> str:
        """Truncate *text* to *max_length* characters."""
        if len(text) <= max_length:
            return text
        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters for Telegram HTML parse mode."""
        import html as _html
        return _html.escape(str(text))

    @staticmethod
    def number_with_commas(value: int | float) -> str:
        """Format a number with thousands separators: 1234567 → '1,234,567'."""
        return f"{value:,}"

    @staticmethod
    def percentage(numerator: float, denominator: float, decimals: int = 1) -> str:
        """Return a percentage string, e.g. '75.0%'. Returns '0%' on zero denominator."""
        if denominator == 0:
            return "0%"
        return f"{numerator / denominator * 100:.{decimals}f}%"


# ---------------------------------------------------------------------------
# CurrencyFormatter
# ---------------------------------------------------------------------------

_CURRENCY_SYMBOLS: dict[str, str] = {
    "MMK": "K",
    "USD": "$",
    "THB": "฿",
    "USDT": "₮",
}


class CurrencyFormatter:
    """Format monetary amounts with currency symbols."""

    @staticmethod
    def format(amount: Decimal | float | int, currency: str) -> str:
        """
        Format *amount* with the currency symbol.

        Example: format(1500.0, "MMK") → "K 1,500.00"

        Args:
            amount:   Monetary value.
            currency: ISO 4217 code (MMK, USD, THB, USDT).

        Returns:
            Formatted string.
        """
        symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency)
        return f"{symbol} {Decimal(str(amount)):,.2f}"

    @staticmethod
    def parse(text: str) -> Decimal:
        """
        Parse a currency string back to a Decimal.

        Strips known symbols, commas, and whitespace.

        Example: "K 1,500.00" → Decimal("1500.00")
        """
        clean = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
        return Decimal(clean)


# ---------------------------------------------------------------------------
# RandomGenerator  (non-cryptographic — use app.core.security for secrets)
# ---------------------------------------------------------------------------

class RandomGenerator:
    """Non-cryptographic random helpers for display IDs, test data, etc."""

    @staticmethod
    def random_string(length: int = 8, alphabet: Optional[str] = None) -> str:
        """Return a random string of *length* from *alphabet*."""
        chars = alphabet or (string.ascii_letters + string.digits)
        return "".join(random.choices(chars, k=length))

    @staticmethod
    def random_int(low: int, high: int) -> int:
        """Return a random integer in [low, high] inclusive."""
        return random.randint(low, high)

    @staticmethod
    def shuffle(items: list[T]) -> list[T]:
        """Return a shuffled copy of *items*."""
        copy = list(items)
        random.shuffle(copy)
        return copy

    @staticmethod
    def choice(items: list[T]) -> T:
        """Return a random element from *items*."""
        return random.choice(items)


# ---------------------------------------------------------------------------
# HashHelper  (non-security, convenience wrappers)
# ---------------------------------------------------------------------------

class HashHelper:
    """Quick hash helpers.  For HMAC / security use app.core.security."""

    @staticmethod
    def md5(text: str) -> str:
        """Return the MD5 hex digest of *text* (not for security purposes)."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()

    @staticmethod
    def sha256(text: str) -> str:
        """Return the SHA-256 hex digest of *text*."""
        import hashlib
        return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# UUIDHelper
# ---------------------------------------------------------------------------

class UUIDHelper:
    """UUID generation and parsing utilities."""

    @staticmethod
    def generate() -> str:
        """Return a new UUIDv4 as a lowercase hyphenated string."""
        return str(uuid.uuid4())

    @staticmethod
    def short() -> str:
        """Return a 12-character hex UUID fragment (for readable IDs)."""
        return uuid.uuid4().hex[:12]

    @staticmethod
    def is_valid(value: str) -> bool:
        """Return True if *value* is a valid UUID string."""
        try:
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False


# ---------------------------------------------------------------------------
# JSONHelper
# ---------------------------------------------------------------------------

class _CustomEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


class JSONHelper:
    """Safe JSON encode/decode with support for Decimal, datetime, and UUID."""

    @staticmethod
    def dumps(obj: Any, *, indent: Optional[int] = None) -> str:
        """Serialise *obj* to a JSON string."""
        return json.dumps(obj, cls=_CustomEncoder, ensure_ascii=False, indent=indent)

    @staticmethod
    def loads(text: str) -> Any:
        """Deserialise JSON *text* to a Python object. Returns None on error."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def safe_loads(text: str, default: Any = None) -> Any:
        """Deserialise JSON *text*, returning *default* on any failure."""
        result = JSONHelper.loads(text)
        return result if result is not None else default


# ---------------------------------------------------------------------------
# FileHelper
# ---------------------------------------------------------------------------

class FileHelper:
    """Path and file utilities."""

    @staticmethod
    def exists(path: str | Path) -> bool:
        """Return True if *path* exists on the filesystem."""
        return Path(path).exists()

    @staticmethod
    def size_human(path: str | Path) -> str:
        """Return the file size as a human-readable string."""
        size = Path(path).stat().st_size
        return Formatter.bytes_to_human(size)

    @staticmethod
    def extension(path: str | Path) -> str:
        """Return the file extension in lowercase (e.g. '.csv')."""
        return Path(path).suffix.lower()

    @staticmethod
    def ensure_dir(path: str | Path) -> Path:
        """Create *path* and all parents if they do not exist."""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def safe_filename(name: str) -> str:
        """Strip characters that are unsafe in filenames."""
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)


# ---------------------------------------------------------------------------
# StringHelper
# ---------------------------------------------------------------------------

class StringHelper:
    """String transformation utilities."""

    @staticmethod
    def slugify(text: str) -> str:
        """
        Convert *text* to a URL-safe slug.

        Example: "Hello, World!" → "hello-world"
        """
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[\s_]+", "-", slug).strip("-")

    @staticmethod
    def camel_to_snake(name: str) -> str:
        """Convert CamelCase to snake_case."""
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        return re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s).lower()

    @staticmethod
    def snake_to_camel(name: str) -> str:
        """Convert snake_case to camelCase."""
        parts = name.split("_")
        return parts[0] + "".join(p.capitalize() for p in parts[1:])

    @staticmethod
    def pad_left(text: str, width: int, char: str = " ") -> str:
        """Right-align *text* within *width* characters."""
        return str(text).rjust(width, char)

    @staticmethod
    def mask_middle(text: str, visible: int = 3) -> str:
        """Show *visible* chars at each end; mask the middle with '***'."""
        if len(text) <= visible * 2:
            return "*" * len(text)
        return text[:visible] + "***" + text[-visible:]


# ---------------------------------------------------------------------------
# EnvironmentHelper
# ---------------------------------------------------------------------------

class EnvironmentHelper:
    """Read typed environment variables with defaults."""

    @staticmethod
    def get_str(key: str, default: str = "") -> str:
        """Return the env var *key* as a string, or *default*."""
        return os.getenv(key, default)

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """Return the env var *key* as an integer, or *default*."""
        try:
            return int(os.getenv(key, ""))
        except ValueError:
            return default

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """
        Return the env var *key* as a boolean.

        Truthy values: "1", "true", "yes", "on" (case-insensitive).
        """
        val = os.getenv(key, "").strip().lower()
        if not val:
            return default
        return val in ("1", "true", "yes", "on")

    @staticmethod
    def get_list(key: str, default: Optional[list[str]] = None, sep: str = ",") -> list[str]:
        """Return the env var *key* split on *sep*, stripped of whitespace."""
        val = os.getenv(key, "")
        if not val:
            return default or []
        return [item.strip() for item in val.split(sep) if item.strip()]

    @staticmethod
    def require(key: str) -> str:
        """Return the env var *key* or raise ConfigurationException."""
        val = os.getenv(key, "")
        if not val:
            from app.core.exceptions import ConfigurationException
            raise ConfigurationException(key, "required environment variable is not set")
        return val


# ---------------------------------------------------------------------------
# RetryHelper
# ---------------------------------------------------------------------------

class RetryHelper:
    """Exponential-backoff retry for async callables."""

    @staticmethod
    async def retry_async(
        fn: Callable[..., Any],
        *args: Any,
        retries: int = 3,
        base_delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple[type[Exception], ...] = (Exception,),
        **kwargs: Any,
    ) -> Any:
        """
        Call *fn* with *args* / *kwargs*, retrying on *exceptions*.

        Args:
            fn:         Async callable to invoke.
            retries:    Number of retry attempts (not counting first try).
            base_delay: Initial delay in seconds before first retry.
            backoff:    Multiplier applied to delay after each failure.
            exceptions: Tuple of exception classes to catch and retry.

        Returns:
            Result of *fn* on the first successful call.

        Raises:
            The last exception if all attempts fail.
        """
        delay = base_delay
        last_exc: Exception = Exception("No attempts made")
        for attempt in range(1 + retries):
            try:
                return await fn(*args, **kwargs)
            except exceptions as exc:  # type: ignore[misc]
                last_exc = exc
                if attempt < retries:
                    await asyncio.sleep(delay)
                    delay *= backoff
        raise last_exc
