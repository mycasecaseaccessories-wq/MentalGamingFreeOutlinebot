"""
Directory initialisation utility.

Ensures all required application directories exist before any service
tries to write to them.  Call ensure_directories() once at startup,
before the database and logging are initialised.

Required directories
--------------------
logs/       Application log files (rotating + daily).
database/   SQLite database files for development.
backups/    Automated database / key backups.
temp/       Ephemeral scratch files (cleared on startup in dev mode).
exports/    Admin-generated export files (CSV, JSON reports).
uploads/    User-uploaded files for future features (Phase 4+).

All paths are resolved relative to the project root (the directory
that contains the bot/ folder).

Phase 0.5: Initial implementation.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root is three levels above this file:
# bot/app/utils/directories.py → bot/app/utils → bot/app → bot → (root)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Canonical list of directories that must exist at application startup.
REQUIRED_DIRECTORIES: list[Path] = [
    _PROJECT_ROOT / "logs",
    _PROJECT_ROOT / "database",
    _PROJECT_ROOT / "backups",
    _PROJECT_ROOT / "temp",
    _PROJECT_ROOT / "exports",
    _PROJECT_ROOT / "uploads",
]


def ensure_directories(extra: list[Path] | None = None) -> list[Path]:
    """
    Create all required application directories if they are missing.

    Already-existing directories are left untouched (idempotent).

    Args:
        extra: Optional list of additional paths to create alongside
               the standard set.  Useful for test environments.

    Returns:
        List of Path objects that were newly created (empty if all
        directories already existed).

    Raises:
        PermissionError: If the process lacks write permission for any
                         parent directory.
    """
    targets = list(REQUIRED_DIRECTORIES)
    if extra:
        targets.extend(extra)

    created: list[Path] = []
    for directory in targets:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
            logger.debug("Created directory: %s", directory)
        else:
            logger.debug("Directory exists:  %s", directory)

    if created:
        logger.info(
            "Created %d missing director%s: %s",
            len(created),
            "y" if len(created) == 1 else "ies",
            ", ".join(str(d.name) for d in created),
        )
    else:
        logger.debug("All required directories already exist.")

    return created


def clear_temp_directory() -> int:
    """
    Remove all files from the temp/ directory.

    Called on startup in development mode to prevent temp files from
    accumulating across restarts.  Never called in production.

    Returns:
        Number of files removed.
    """
    temp_dir = _PROJECT_ROOT / "temp"
    if not temp_dir.exists():
        return 0

    removed = 0
    for file in temp_dir.iterdir():
        if file.is_file():
            try:
                file.unlink()
                removed += 1
            except OSError as exc:
                logger.warning("Could not remove temp file %s: %s", file, exc)

    if removed:
        logger.info("Cleared %d file(s) from temp/", removed)
    return removed


def get_directory(name: str) -> Path:
    """
    Return the absolute path for a named application directory.

    Args:
        name: One of 'logs', 'database', 'backups', 'temp', 'exports', 'uploads'.

    Returns:
        Absolute Path to the directory.

    Raises:
        KeyError: If *name* is not a known directory.
    """
    mapping: dict[str, Path] = {
        d.name: d for d in REQUIRED_DIRECTORIES
    }
    if name not in mapping:
        raise KeyError(
            f"Unknown directory {name!r}. "
            f"Known: {sorted(mapping.keys())}"
        )
    return mapping[name]
