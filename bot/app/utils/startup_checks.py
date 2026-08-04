"""
Application startup pre-flight checks.

Runs a series of fast validation checks before the bot starts accepting
Telegram updates.  Any critical failure raises StartupError, which
Bootstrap catches to log and exit cleanly.

Checks performed
----------------
1. BOT_TOKEN       — required env var present and non-empty.
2. Database        — URL is set and the DB file / server is reachable.
3. Directories     — all required directories exist (created if missing).
4. Configuration   — critical settings have valid values.
5. Localisation    — at least one locale file is loadable.

Usage:
    from app.utils.startup_checks import run_all_checks, StartupError
    try:
        await run_all_checks(settings, db)
    except StartupError as exc:
        logger.critical("Startup check failed: %s", exc)
        sys.exit(1)

Phase 0.5: Full implementation.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class StartupError(RuntimeError):
    """
    Raised when a critical startup check fails.

    Bootstrap catches this exception, logs it at CRITICAL level, and
    exits the process cleanly without a noisy traceback.
    """


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_bot_token() -> None:
    """
    Verify that BOT_TOKEN is set and non-empty.

    Raises:
        StartupError: If BOT_TOKEN is missing or blank.
    """
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise StartupError(
            "BOT_TOKEN environment variable is not set. "
            "Add it to your .env file or Replit Secrets."
        )
    # Minimal format check: Telegram tokens are "<id>:<alphanumeric>".
    if ":" not in token or len(token) < 20:
        raise StartupError(
            "BOT_TOKEN does not look like a valid Telegram bot token. "
            "Expected format: '123456789:ABCdef…'"
        )
    logger.debug("check_bot_token: OK")


async def check_database(db) -> None:
    """
    Verify the database is reachable by executing a simple query.

    Args:
        db: Initialised DatabaseManager instance.

    Raises:
        StartupError: If the database connection or query fails.
    """
    try:
        from sqlalchemy import text
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        logger.debug("check_database: OK")
    except Exception as exc:
        raise StartupError(
            f"Database is not reachable: {exc}"
        ) from exc


def check_directories() -> None:
    """
    Ensure all required application directories exist (create if missing).

    Raises:
        StartupError: If a directory cannot be created (permission error, etc.).
    """
    try:
        from app.utils.directories import ensure_directories
        ensure_directories()
        logger.debug("check_directories: OK")
    except PermissionError as exc:
        raise StartupError(
            f"Cannot create required directories: {exc}"
        ) from exc


def check_configuration(settings) -> None:
    """
    Validate critical configuration values.

    Args:
        settings: Application Settings instance.

    Raises:
        StartupError: If a critical setting is missing or invalid.
    """
    errors: list[str] = []

    # Environment must be one of the known values.
    valid_envs = {"development", "staging", "production"}
    if settings.environment not in valid_envs:
        errors.append(
            f"ENVIRONMENT={settings.environment!r} is not valid. "
            f"Valid: {sorted(valid_envs)}"
        )

    # Timezone should be a non-empty string.
    if not getattr(settings, "timezone", "").strip():
        errors.append("TIMEZONE is empty — set a valid IANA timezone (e.g. 'Asia/Rangoon').")

    # Default language must be supported.
    supported_langs = {"en", "my"}
    lang = getattr(settings, "default_language", "en")
    if lang not in supported_langs:
        errors.append(
            f"DEFAULT_LANGUAGE={lang!r} is not supported. "
            f"Supported: {sorted(supported_langs)}"
        )

    if errors:
        raise StartupError(
            "Configuration errors:\n" + "\n".join(f"  • {e}" for e in errors)
        )

    logger.debug("check_configuration: OK")


def check_localization() -> None:
    """
    Verify that locale translation modules can be imported and are non-empty.

    Raises:
        StartupError: If any locale fails to load or is empty.
    """
    errors: list[str] = []

    for lang_code in ("en", "my"):
        try:
            from locales.translator import _get_registry
            registry = _get_registry()
            translations = registry.get(lang_code, {})
            if not translations:
                errors.append(
                    f"Locale '{lang_code}' loaded but has no translations."
                )
            else:
                logger.debug(
                    "check_localization: '%s' OK (%d keys)", lang_code, len(translations)
                )
        except Exception as exc:
            errors.append(f"Failed to load locale '{lang_code}': {exc}")

    if errors:
        raise StartupError(
            "Localisation errors:\n" + "\n".join(f"  • {e}" for e in errors)
        )

    logger.debug("check_localization: OK")


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------

async def run_all_checks(settings, db=None) -> None:
    """
    Execute all pre-flight checks in order.

    Runs synchronous checks first, then async checks (database).
    Stops at the first critical failure and re-raises StartupError.

    Args:
        settings: Application Settings instance.
        db:       Optional initialised DatabaseManager (required for DB check).

    Raises:
        StartupError: On the first check that fails.
    """
    checks = [
        ("BOT_TOKEN",      lambda: check_bot_token()),
        ("Directories",    lambda: check_directories()),
        ("Configuration",  lambda: check_configuration(settings)),
        ("Localisation",   lambda: check_localization()),
    ]

    for name, fn in checks:
        logger.info("  ✓ Checking %s…", name)
        fn()

    if db is not None:
        logger.info("  ✓ Checking Database…")
        await check_database(db)

    logger.info("All startup checks passed.")
