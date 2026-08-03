"""
Alembic async migration environment.

Supports:
  • Offline mode  — generates SQL without a live DB connection.
  • Online mode   — applies migrations directly using the async engine.

The database URL is resolved (in order of priority):
  1. Config option set programmatically (e.g. via DatabaseManager).
  2. BOT_DATABASE_URL environment variable.
  3. sqlite+aiosqlite:///./data/mental_vpn.db  (development default).

Auto-upgrade sync schemes to async equivalents (sqlite:// → sqlite+aiosqlite://).
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ── Make sure the bot/ root is on sys.path ────────────────────────────────────
# Required when running `alembic` from inside the bot/ directory so that
# `from database.base import Base` resolves correctly.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Import ORM metadata ────────────────────────────────────────────────────────
# Importing database.models registers every mapped class with Base.metadata.
import database.models  # noqa: F401 — side-effect import
from database.base import Base

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Apply logging configuration from alembic.ini (if running via CLI).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_url() -> str:
    """
    Return the database URL to use for migrations.

    Priority:
      1. sqlalchemy.url set via config.set_main_option() (programmatic callers).
      2. BOT_DATABASE_URL environment variable.
      3. Hard-coded SQLite development default.
    """
    url = config.get_main_option("sqlalchemy.url") or ""
    if not url:
        url = os.getenv("BOT_DATABASE_URL", "sqlite+aiosqlite:///./data/mental_vpn.db")
    # Upgrade sync scheme prefixes to async equivalents.
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
    return url


def _do_run_migrations(connection) -> None:
    """
    Configure the migration context and execute pending migrations.

    render_as_batch=True enables SQLite-compatible column alterations
    (CREATE TABLE … copy … DROP … RENAME).
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,   # Required for SQLite ALTER TABLE support.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Offline mode  (alembic upgrade --sql  or  alembic revision --autogenerate)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode  (alembic upgrade head  or  programmatic call)
# ---------------------------------------------------------------------------

async def _run_async_migrations() -> None:
    """Connect to the database asynchronously and apply migrations."""
    url = _resolve_url()
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    """Entry point for synchronous alembic CLI calls."""
    asyncio.run(_run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
