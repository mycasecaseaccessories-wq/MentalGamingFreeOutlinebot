"""
Security utilities.

Reusable helpers for secrets handling, input sanitisation, token
generation, and permission checking.  No business logic here — only
pure security infrastructure.

Usage:
    from app.core.security import mask_secret, generate_token, hash_value

    safe_log = mask_secret(api_key)
    token    = generate_token(32)
    digest   = hash_value("password", salt)
"""

from __future__ import annotations

import hashlib
import hmac
import html
import os
import re
import secrets
import string
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Secret masking
# ---------------------------------------------------------------------------

def mask_secret(value: str, *, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    Partially mask a secret for safe logging.

    Shows the first and last *visible_chars* characters; replaces the
    middle with mask characters.

    Args:
        value:         The secret string to mask.
        visible_chars: How many characters to expose at each end (max 4).
        mask_char:     Character to use for masking.

    Returns:
        Masked string, e.g. "abc****xyz".

    Example:
        >>> mask_secret("1234567890abcdef")
        "1234********cdef"
    """
    if not value:
        return ""
    n = len(value)
    v = min(visible_chars, max(0, n // 4))  # Never expose > 25 % of the value
    if n <= v * 2:
        return mask_char * n
    middle_len = max(4, n - v * 2)
    return value[:v] + mask_char * middle_len + value[n - v:]


def mask_token(token: str) -> str:
    """Mask a bearer/API token, keeping exactly the first eight characters."""
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return token[:8] + "*" * (len(token) - 8)


def mask_database_url(url: str) -> str:
    """
    Remove credentials from a database URL for safe logging.

    Replaces ``user:password@`` with ``***@``.

    Example:
        "postgresql+asyncpg://user:secret@host:5432/db"
        → "postgresql+asyncpg://***@host:5432/db"
    """
    return re.sub(r"://[^@]+@", "://***@", url)


# ---------------------------------------------------------------------------
# Sensitive data filter (for log records)
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(bot_token[=:\s]+)[^\s&\"']+",    re.IGNORECASE), r"\1***"),
    (re.compile(r"(password[=:\s]+)[^\s&\"']+",     re.IGNORECASE), r"\1***"),
    (re.compile(r"(secret[=:\s]+)[^\s&\"']+",       re.IGNORECASE), r"\1***"),
    (re.compile(r"(token[=:\s]+)[^\s&\"']+",        re.IGNORECASE), r"\1***"),
    (re.compile(r"(api_key[=:\s]+)[^\s&\"']+",      re.IGNORECASE), r"\1***"),
    (re.compile(r"\d{8,10}:[A-Za-z0-9_\-]{35}"),                    "***BOT_TOKEN***"),
]


def redact_sensitive(text: str) -> str:
    """
    Replace known sensitive patterns in *text* with redacted placeholders.

    Safe to call on log messages, error strings, and repr() output.

    Args:
        text: Input string that may contain secrets.

    Returns:
        Redacted string.
    """
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------

def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters for safe use in Telegram HTML parse mode.

    Escapes: & < > "

    Returns:
        HTML-safe string.
    """
    return html.escape(str(text))


def sanitize_text(text: str, *, max_length: int = 4096) -> str:
    """
    Strip leading/trailing whitespace, collapse internal runs of whitespace,
    and truncate to *max_length* characters.

    Args:
        text:       Raw user input.
        max_length: Maximum allowed length after normalisation.

    Returns:
        Cleaned string.
    """
    clean = re.sub(r"\s+", " ", str(text).strip())
    return clean[:max_length]


def strip_control_chars(text: str) -> str:
    """
    Remove ASCII control characters (0x00–0x1F except tab, newline, CR).

    Prevents log injection and malformed Telegram messages.

    Returns:
        Cleaned string.
    """
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


# ---------------------------------------------------------------------------
# Secure random generation
# ---------------------------------------------------------------------------

def generate_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure URL-safe token.

    Uses ``secrets.token_urlsafe`` which outputs base64-encoded bytes.

    Args:
        length: Minimum character length of the token.

    Returns:
        URL-safe random string of at least *length* characters.
    """
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    """
    Generate a numeric one-time password.

    Args:
        length: Number of digits (default 6).

    Returns:
        Zero-padded numeric string.
    """
    max_val = 10 ** length
    return str(secrets.randbelow(max_val)).zfill(length)


def generate_referral_code(length: int = 8) -> str:
    """
    Generate a short alphanumeric referral code (uppercase, no ambiguous chars).

    Excluded characters: 0, O, I, l, 1 (easily confused).

    Args:
        length: Code length (default 8).

    Returns:
        Uppercase alphanumeric string.
    """
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def secure_random_bytes(n: int) -> bytes:
    """Return *n* cryptographically secure random bytes."""
    return os.urandom(n)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_value(value: str, salt: Optional[str] = None, *, algorithm: str = "sha256") -> str:
    """
    Hash *value* with an optional *salt* using the specified algorithm.

    Args:
        value:     Plain-text value to hash.
        salt:      Optional salt prepended to value before hashing.
        algorithm: Hash algorithm name (sha256, sha512, md5, …).

    Returns:
        Hex digest string.
    """
    raw = f"{salt}:{value}" if salt else value
    h = hashlib.new(algorithm, raw.encode("utf-8"))
    return h.hexdigest()


def hmac_sign(message: str, secret: str, *, algorithm: str = "sha256") -> str:
    """
    Compute an HMAC signature for *message* using *secret*.

    Args:
        message:   The data to sign.
        secret:    Shared secret key.
        algorithm: Hash algorithm (sha256, sha512).

    Returns:
        Hex HMAC digest.
    """
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        algorithm,
    ).hexdigest()


def hmac_verify(message: str, signature: str, secret: str, *, algorithm: str = "sha256") -> bool:
    """
    Verify an HMAC signature using a constant-time comparison.

    Returns:
        True if the signature is valid.
    """
    expected = hmac_sign(message, secret, algorithm=algorithm)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Permission checker
# ---------------------------------------------------------------------------

def check_permission(user_role: str, required_permission: str) -> bool:
    """
    Return True if *user_role* grants *required_permission*.

    Reads the ROLE_PERMISSIONS mapping from app.models.enums at call time
    (lazy import avoids circular dependencies).

    Args:
        user_role:           Role string (e.g. "admin", "customer").
        required_permission: Permission string (e.g. "manage_users").

    Returns:
        True if the role includes the permission.
    """
    from app.models.enums import ROLE_PERMISSIONS
    permissions = ROLE_PERMISSIONS.get(user_role, [])
    return required_permission in permissions


def require_permission(user_role: str, required_permission: str) -> None:
    """
    Assert that *user_role* grants *required_permission*.

    Raises:
        PermissionDeniedException: If the permission is not granted.
    """
    if not check_permission(user_role, required_permission):
        from app.core.exceptions import PermissionDeniedException
        raise PermissionDeniedException(required_permission)
