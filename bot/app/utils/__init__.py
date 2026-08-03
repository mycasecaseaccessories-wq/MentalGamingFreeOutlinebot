"""
Utilities package.

Shared helpers that do not belong to a specific domain layer.

Modules:
    logger   — Logging configuration and factory function.
    helpers  — Miscellaneous helper functions.
"""

from .logger import setup_logging, get_logger
from .helpers import escape_html, truncate

__all__ = ["setup_logging", "get_logger", "escape_html", "truncate"]
