"""
Reusable input validators.

All validators follow the same contract:
  - Accept a raw value.
  - Return the cleaned/normalised value on success.
  - Raise ValidationException on failure (never return None silently).

Usage:
    from app.core.validators import validate_telegram_id, validate_price

    tg_id = validate_telegram_id(update.effective_user.id)
    price = validate_price("12.50")
"""

from __future__ import annotations

import json
import re
import uuid as _uuid_module
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.exceptions import ValidationException


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def validate_telegram_id(value: Any) -> int:
    """
    Validate and return a Telegram user or chat ID.

    Telegram IDs are positive or negative non-zero integers.
    Bot IDs are positive; group/channel IDs are negative.

    Args:
        value: Raw value (int or string).

    Returns:
        Validated integer ID.

    Raises:
        ValidationException: If value is not a valid Telegram ID.
    """
    try:
        int_val = int(value)
    except (TypeError, ValueError):
        raise ValidationException("telegram_id", "must be an integer", value)
    if int_val == 0:
        raise ValidationException("telegram_id", "must not be zero", value)
    return int_val


def validate_username(value: Optional[str]) -> Optional[str]:
    """
    Validate a Telegram @username (without the '@' prefix).

    Returns None when value is None or empty (username is optional).

    Raises:
        ValidationException: If the username contains illegal characters.
    """
    if not value:
        return None
    clean = value.lstrip("@").strip()
    if not re.fullmatch(r"[a-zA-Z0-9_]{5,32}", clean):
        raise ValidationException(
            "username",
            "must be 5–32 characters, alphanumeric and underscores only",
            value,
        )
    return clean


# ---------------------------------------------------------------------------
# Commerce
# ---------------------------------------------------------------------------

def validate_price(value: Any, *, allow_zero: bool = False) -> Decimal:
    """
    Validate a monetary amount and return a Decimal.

    Args:
        value:      Raw value (str, int, float, or Decimal).
        allow_zero: When False (default), rejects 0.

    Returns:
        Decimal with 2 decimal places.

    Raises:
        ValidationException: If the value is not a valid non-negative number.
    """
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValidationException("price", "must be a valid decimal number", value)
    if d < 0:
        raise ValidationException("price", "must not be negative", value)
    if not allow_zero and d == 0:
        raise ValidationException("price", "must be greater than zero", value)
    return d


def validate_gb(value: Any, *, allow_zero: bool = True) -> float:
    """
    Validate a data-limit value in gigabytes.

    0 is allowed by default and means "unlimited".

    Returns:
        Float rounded to 2 decimal places.

    Raises:
        ValidationException: If value is negative or not numeric.
    """
    try:
        f = round(float(value), 2)
    except (TypeError, ValueError):
        raise ValidationException("data_limit_gb", "must be a numeric value", value)
    if f < 0:
        raise ValidationException("data_limit_gb", "must not be negative", value)
    if not allow_zero and f == 0.0:
        raise ValidationException("data_limit_gb", "must be greater than zero", value)
    return f


def validate_duration_days(value: Any) -> int:
    """
    Validate a subscription duration in whole days (1–3650).

    Returns:
        Integer number of days.

    Raises:
        ValidationException: If value is out of range or not an integer.
    """
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValidationException("duration_days", "must be an integer", value)
    if days < 1:
        raise ValidationException("duration_days", "must be at least 1 day", value)
    if days > 3_650:
        raise ValidationException("duration_days", "must not exceed 3650 days (10 years)", value)
    return days


def validate_currency(value: str) -> str:
    """
    Validate an ISO 4217 currency code.

    Returns:
        Uppercase currency code.

    Raises:
        ValidationException: If the code is not supported.
    """
    from app.core.constants import SUPPORTED_CURRENCIES
    code = str(value).strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise ValidationException(
            "currency",
            f"must be one of {SUPPORTED_CURRENCIES}",
            value,
        )
    return code


# ---------------------------------------------------------------------------
# Package / catalogue
# ---------------------------------------------------------------------------

def validate_package_name(value: str) -> str:
    """
    Validate a package display name (2–64 characters, printable).

    Returns:
        Stripped package name.

    Raises:
        ValidationException: If the name is blank or too long.
    """
    clean = str(value).strip()
    if len(clean) < 2:
        raise ValidationException("package_name", "must be at least 2 characters", value)
    if len(clean) > 64:
        raise ValidationException("package_name", "must not exceed 64 characters", value)
    return clean


# ---------------------------------------------------------------------------
# Geographic / locale
# ---------------------------------------------------------------------------

def validate_country_code(value: str) -> str:
    """
    Validate an ISO 3166-1 alpha-2 country code.

    Returns:
        Uppercase two-letter code (e.g. "SG", "MM").

    Raises:
        ValidationException: If the code is not two ASCII letters.
    """
    code = str(value).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise ValidationException(
            "country_code",
            "must be a two-letter ISO 3166-1 alpha-2 code (e.g. 'MM', 'SG')",
            value,
        )
    return code


def validate_timezone(value: str) -> str:
    """
    Validate an IANA timezone string.

    Only checks that the string is in the supported list for the platform.

    Returns:
        Validated timezone string.

    Raises:
        ValidationException: If the timezone is not supported.
    """
    from app.core.constants import SUPPORTED_TIMEZONES
    tz = str(value).strip()
    if tz not in SUPPORTED_TIMEZONES:
        raise ValidationException(
            "timezone",
            f"must be one of {SUPPORTED_TIMEZONES}",
            value,
        )
    return tz


def validate_language(value: str) -> str:
    """
    Validate a supported UI language code.

    Returns:
        Lowercase language code.

    Raises:
        ValidationException: If the code is not supported.
    """
    from app.core.constants import SUPPORTED_LANGUAGES
    code = str(value).strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        raise ValidationException(
            "language",
            f"must be one of {SUPPORTED_LANGUAGES}",
            value,
        )
    return code


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

def validate_uuid(value: Any) -> str:
    """
    Validate and normalise a UUID string (any format, case-insensitive).

    Returns:
        Lowercase hyphenated UUID string.

    Raises:
        ValidationException: If value is not a valid UUID.
    """
    try:
        parsed = _uuid_module.UUID(str(value))
        return str(parsed)
    except (ValueError, AttributeError):
        raise ValidationException("uuid", "must be a valid UUID", value)


def validate_email(value: str) -> str:
    """
    Validate an email address (basic format check).

    Returns:
        Lowercase stripped email.

    Raises:
        ValidationException: If the format is invalid.
    """
    clean = str(value).strip().lower()
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.fullmatch(pattern, clean):
        raise ValidationException("email", "must be a valid email address", value)
    return clean


def validate_url(value: str, *, schemes: tuple[str, ...] = ("http", "https")) -> str:
    """
    Validate a URL.

    Args:
        value:   Raw URL string.
        schemes: Allowed URL schemes.

    Returns:
        Stripped URL string.

    Raises:
        ValidationException: If the URL is malformed or uses a disallowed scheme.
    """
    clean = str(value).strip()
    try:
        parsed = urlparse(clean)
        if parsed.scheme not in schemes or not parsed.netloc:
            raise ValidationException(
                "url",
                f"must be a valid URL with scheme in {schemes}",
                value,
            )
    except Exception as exc:
        if isinstance(exc, ValidationException):
            raise
        raise ValidationException("url", "must be a valid URL", value) from exc
    return clean


def validate_json(value: str) -> Any:
    """
    Validate and parse a JSON string.

    Returns:
        Parsed Python object.

    Raises:
        ValidationException: If the string is not valid JSON.
    """
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationException("json", f"invalid JSON: {exc}", value) from exc


def validate_positive_int(field: str, value: Any, *, max_value: Optional[int] = None) -> int:
    """
    Validate a positive integer.

    Args:
        field:     Field name used in the exception message.
        value:     Raw value.
        max_value: Optional upper bound.

    Returns:
        Validated positive integer.

    Raises:
        ValidationException: If validation fails.
    """
    try:
        int_val = int(value)
    except (TypeError, ValueError):
        raise ValidationException(field, "must be an integer", value)
    if int_val <= 0:
        raise ValidationException(field, "must be a positive integer", value)
    if max_value is not None and int_val > max_value:
        raise ValidationException(field, f"must not exceed {max_value}", value)
    return int_val
