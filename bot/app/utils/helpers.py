"""
Miscellaneous helper functions.

Keep this module lean — only add utilities that are truly generic
and used in more than one place.
"""

from __future__ import annotations

import html as _html
from typing import Optional


def escape_html(text: str) -> str:
    """
    Escape special HTML characters for safe use in Telegram HTML parse mode.

    Escapes: & < > "

    Args:
        text: Raw text that may contain HTML special characters.

    Returns:
        HTML-safe string.

    Example:
        >>> escape_html("<b>Hello & World</b>")
        '&lt;b&gt;Hello &amp; World&lt;/b&gt;'
    """
    return _html.escape(text)


def truncate(text: str, max_length: int = 100, suffix: str = "…") -> str:
    """
    Truncate text to max_length characters, appending suffix if truncated.

    Args:
        text:       Input string.
        max_length: Maximum number of characters (including suffix).
        suffix:     String appended when truncation occurs.

    Returns:
        The (possibly truncated) string.

    Example:
        >>> truncate("Hello, World!", max_length=8)
        'Hello, …'
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_bytes(num_bytes: int) -> str:
    """
    Convert a byte count into a human-readable string.

    Args:
        num_bytes: Size in bytes.

    Returns:
        Formatted string such as '1.5 GB', '512 MB', '4.2 KB'.

    Example:
        >>> format_bytes(1_500_000_000)
        '1.40 GB'
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"
