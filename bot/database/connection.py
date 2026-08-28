"""
Database connection management.

Provides a DatabaseManager singleton that owns the SQLAlchemy async engine
and session factory.

Supported databases (selected via DATABASE_URL):
  sqlite+aiosqlite:///./data/mental_vpn.db  — development default
  postgresql+asyncpg://user:pass@host/db    — production

Usage:
    from database import DatabaseManager

    db = DatabaseManager.get_instance()
    await db.init()

    async with db.session() as session:
        result = await session.execute(select(UserORM))
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# SQLAlchemy async imports are deferred to init() so missing packages
# produce a clean error message rather than an ImportError at module load.
try:
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    _SQLALCHEMY_AVAILABLE = True
except ImportError:
    _SQLALCHEMY_AVAILABLE = False
    logger.warning(
        "SQLAlchemy async is not installed. "
        "Install sqlalchemy[asyncio] and aiosqlite (or asyncpg) to enable the database."
    )


class DatabaseManager:
    """
    Singleton database connection manager.

    Lifecycle:
      1. get_instance()  — retrieve (or create) the singleton.
      2. await init()    — create engine + session factory; run CREATE TABLE IF NOT EXISTS.
      3. session()       — async context manager yielding a session per operation.
      4. await close()   — dispose engine on shutdown.
    """

    _instance: Optional["DatabaseManager"] = None

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Optional["AsyncEngine"] = None
        self._session_factory: Optional["async_sessionmaker[AsyncSession]"] = None

    # ── Singleton access ───────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        """
        Return the application-wide DatabaseManager instance.

        Raises RuntimeError if initialise() was never called.
        """
        if cls._instance is None:
            raise RuntimeError(
                "DatabaseManager has not been initialised. "
                "Call DatabaseManager.initialise(database_url) first."
            )
        return cls._instance

    @classmethod
    def initialise(cls, database_url: str) -> "DatabaseManager":
        """
        Create and store the singleton instance.

        Args:
            database_url: SQLAlchemy async connection URL.

        Returns:
            The newly created DatabaseManager instance.
        """
        if cls._instance is not None:
            logger.warning("DatabaseManager.initialise() called more than once — ignoring.")
            return cls._instance
        cls._instance = cls(database_url)
        logger.info("DatabaseManager initialised — url_scheme=%s", database_url.split("://")[0])
        return cls._instance

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def init(self) -> None:
        """
        Create the async engine and session factory, then apply migrations.

        Startup sequence:
          1. Create the SQLAlchemy engine and session factory.
          2. Run Alembic migrations to bring the schema to HEAD.
             • Fresh databases: all tables are created by the initial migration.
             • Phase 0.2 databases (created with create_all, no alembic_version
               table): automatically detected and stamped at revision 0001,
               then upgraded to HEAD.

        Call once at application startup.
        """
        if not _SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy async is required. See database/connection.py.")

        import database.models  # noqa: F401 — registers all ORM models with Base.metadata

        # SQLite needs check_same_thread=False via connect_args.
        connect_args = {}
        if self._database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self._engine = create_async_engine(
            self._database_url,
            echo=False,
            connect_args=connect_args,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Apply Alembic migrations (handles both new and existing databases).
        await self._run_migrations()

        logger.info("Database connection established and schema at HEAD.")

    async def _run_migrations(self) -> None:
        """
        Apply all pending Alembic migrations to the database.

        Handles three scenarios:
          A. Brand-new database  — runs every migration from 0001 to HEAD.
          B. Phase 0.2 database  — tables exist but no alembic_version row;
             stamps the DB at revision 0001 then upgrades to HEAD.
          C. Versioned database  — already tracked by Alembic; runs only
             the migrations that are newer than the current revision.

        Alembic is invoked in a thread-pool executor so that the async event
        loop is not blocked.  The thread-local asyncio.run() inside env.py
        is safe because the executor thread has no running event loop.
        """
        import asyncio
        from pathlib import Path
        from sqlalchemy import text

        # ── Detect unversioned Phase 0.2 databases ────────────────────────────
        needs_stamp = await self._needs_phase02_stamp()

        # ── Run Alembic in thread pool (sync API) ─────────────────────────────
        ini_path = Path(__file__).parent.parent / "alembic.ini"

        def _upgrade() -> None:
            try:
                from alembic.config import Config
                from alembic import command as alembic_command

                cfg = Config(str(ini_path))
                cfg.set_main_option("sqlalchemy.url", self._database_url)

                if needs_stamp:
                    # Stamp the Phase 0.2 baseline so Alembic knows which
                    # migrations have already been applied implicitly.
                    logger.info(
                        "Detected unversioned Phase 0.2 database — "
                        "stamping at revision 0001 before upgrading."
                    )
                    alembic_command.stamp(cfg, "0001")

                alembic_command.upgrade(cfg, "head")
                logger.info("Alembic migrations applied — schema is at HEAD.")

            except ImportError as exc:
                # Never silently bootstrap a production database outside migrations.
                if not self._database_url.startswith("sqlite"):
                    raise RuntimeError(
                        "Alembic is required for non-SQLite database startup."
                    ) from exc
                logger.warning(
                    "Alembic is not installed — using create_all() only for "
                    "the SQLite development/test database."
                )
                import asyncio as _asyncio

                _asyncio.run(self._create_all_fallback())

        await asyncio.to_thread(_upgrade)

    async def _needs_phase02_stamp(self) -> bool:
        """
        Return True if the database has Phase 0.2 tables but no alembic_version.

        This indicates a database created with create_all() before Alembic was
        wired in.  We stamp it at revision 0001 so Alembic skips re-creating
        the base tables and only applies newer migrations.
        """
        from sqlalchemy import text

        is_sqlite = "sqlite" in self._database_url

        async with self._engine.connect() as conn:
            # Check for alembic_version table.
            if is_sqlite:
                result = await conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='alembic_version'"
                    )
                )
            else:
                result = await conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname='public' AND tablename='alembic_version'"
                    )
                )
            if result.scalar() is not None:
                return False  # Already tracked — no stamp needed.

            # Stamp only a complete unversioned Phase 0.2 database. A partial
            # database (for example, one containing only settings from a test
            # fixture) must run the base migration instead of skipping table
            # creation and failing on a later ALTER TABLE.
            # Legacy fixtures and early Phase 0.2 deployments may contain only
            # the core tables touched by the first follow-up migrations.  Those
            # databases must still be stamped rather than replaying 0001.
            required_tables = {
                "users", "roles", "packages", "servers", "vpn_keys", "wallets",
                "orders", "transactions", "referrals", "free_trials", "settings",
                "notifications", "audit_logs",
            }
            if is_sqlite:
                result = await conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                )
            else:
                result = await conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname='public'"
                    )
                )
            existing_tables = {row[0] for row in result.fetchall()}
            return required_tables.issubset(existing_tables)

    async def _create_all_fallback(self) -> None:
        """Fallback: create all tables via metadata.create_all (no migration tracking)."""
        from database.base import Base
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator["AsyncSession", None]:
        """
        Async context manager providing a database session.

        Commits on success, rolls back on exception, always closes the session.

        Usage:
            async with db.session() as session:
                result = await session.execute(...)
        """
        if self._session_factory is None:
            raise RuntimeError("DatabaseManager.init() must be awaited before use.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Dispose the async engine and release all connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connection pool closed.")
