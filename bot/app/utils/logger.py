"""
Logging configuration.

Call setup_logging() once at application startup (in main.py).
Everywhere else, obtain a logger with:

    import logging
    logger = logging.getLogger(__name__)

This ensures consistent formatting, log level, and file output across
the entire application.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path


_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_FILE = _LOG_DIR / "bot.log"


def setup_logging(level: str = "INFO") -> None:
    """
    Configure the root logger for the application.

    Sets up:
      • Console handler   — coloured output to stdout.
      • Rotating file handler — up to 5 × 10 MB files in logs/.

    Args:
        level: Logging level string (DEBUG / INFO / WARNING / ERROR / CRITICAL).

    Call this ONCE at the very start of main.py before any other imports
    that may use logging.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Ensure the logs directory exists.
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Shared formatter.
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(numeric_level)

    # Rotating file handler (max 10 MB × 5 backup files).
    file_handler = logging.handlers.RotatingFileHandler(
        filename=_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)  # Always capture DEBUG to file.

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Let handlers filter by their own level.
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silence overly verbose third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialised — level=%s log_file=%s", level, _LOG_FILE
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Convenience wrapper; identical to logging.getLogger(name).
    """
    return logging.getLogger(name)
