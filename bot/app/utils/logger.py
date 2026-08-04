"""
Logging configuration.

Call setup_logging() once at application startup (in main.py / Bootstrap).
Everywhere else, obtain a logger with:

    import logging
    logger = logging.getLogger(__name__)

Phase 0.5 improvements over Phase 0.3:
  • Daily rotating log files (TimedRotatingFileHandler) in addition to
    the existing size-based RotatingFileHandler.
  • Log format includes function name for easier debugging.
  • is_development flag switches console handler to DEBUG level.
  • All five standard levels documented and handled.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


# Default log directory: project_root/logs/ (three levels up from this file).
_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_FILE_ROTATING = _LOG_DIR / "bot.log"            # size-based rotation
_LOG_FILE_DAILY    = _LOG_DIR / "bot_daily.log"      # time-based rotation


def setup_logging(level: str = "INFO", is_development: bool = False) -> None:
    """
    Configure the root logger for the application.

    Sets up three handlers:
      • Console handler         — stdout, level=level (DEBUG in dev mode).
      • Rotating file handler   — up to 5 × 10 MB files, always at DEBUG.
      • Daily rotating handler  — one file per day, kept for 30 days.

    Log format:
        2025-08-04 12:00:00 | INFO     | module.submodule:function_name | message

    Args:
        level:          Logging level string for the console handler.
                        One of: DEBUG / INFO / WARNING / ERROR / CRITICAL.
        is_development: When True, console handler is set to DEBUG regardless
                        of *level*, giving verbose output during development.

    Notes:
        Call this ONCE at the very start of main.py before any module that
        uses logging is imported.  Calling it more than once appends
        duplicate handlers; protect with a guard if needed.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    console_level = logging.DEBUG if is_development else numeric_level

    # ── Shared formatter ───────────────────────────────────────────────────
    # Includes: timestamp, level, module:function, message.
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(console_level)

    # ── Rotating file handler (size-based, 10 MB × 5) ─────────────────────
    rotating_handler = logging.handlers.RotatingFileHandler(
        filename=_LOG_FILE_ROTATING,
        maxBytes=10 * 1024 * 1024,   # 10 MB per file
        backupCount=5,
        encoding="utf-8",
    )
    rotating_handler.setFormatter(fmt)
    rotating_handler.setLevel(logging.DEBUG)

    # ── Daily rotating file handler (one file per day, 30 days) ───────────
    daily_handler = logging.handlers.TimedRotatingFileHandler(
        filename=_LOG_FILE_DAILY,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    daily_handler.setFormatter(fmt)
    daily_handler.setLevel(logging.DEBUG)

    # ── Root logger ────────────────────────────────────────────────────────
    root_logger = logging.getLogger()

    # Guard against duplicate handler registration on re-import / re-init.
    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.setLevel(logging.DEBUG)  # Handlers filter their own levels.
    root_logger.addHandler(console_handler)
    root_logger.addHandler(rotating_handler)
    root_logger.addHandler(daily_handler)

    # ── Silence verbose third-party loggers ───────────────────────────────
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _logger = logging.getLogger(__name__)
    _logger.info(
        "Logging initialised — level=%s dev_mode=%s log_dir=%s",
        level, is_development, _LOG_DIR,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Convenience wrapper — identical to logging.getLogger(name).

    Args:
        name: Logger name, typically __name__ of the calling module.
    """
    return logging.getLogger(name)
