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
        Create the async engine and session factory.

        Also creates all tables defined in ORM models (CREATE TABLE IF NOT EXISTS).
        Call once at application startup.
        """
        if not _SQLALCHEMY_AVAILABLE:
            raise RuntimeError("SQLAlchemy async is required. See database/connection.py.")

        from database.base import Base  # local import to avoid circular deps

        # SQLite needs check_same_thread=False workaround via connect_args.
        connect_args = {}
        if self._database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        self._engine = create_async_engine(
            self._database_url,
            echo=False,  # Set True to log all SQL queries (dev only).
            connect_args=connect_args,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create all tables (idempotent).
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database connection established and schema applied.")

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
