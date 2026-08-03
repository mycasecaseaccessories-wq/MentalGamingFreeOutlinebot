"""
Database session helpers.

Provides lightweight wrappers around the DatabaseManager so that service
and repository code can obtain an async session with minimal boilerplate.

Usage:
    from database.session import get_session

    async with get_session() as session:
        result = await session.execute(select(UserORM))

Alternatively, inject the DatabaseManager directly for full control:
    from database import DatabaseManager
    db = DatabaseManager.get_instance()
    async with db.session() as session:
        ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import DatabaseManager


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a committed, auto-rolled-back session.

    Delegates to DatabaseManager.session() so all session lifecycle
    (commit on success, rollback on exception, close) is handled centrally.

    Example:
        async with get_session() as session:
            user = await session.get(UserORM, user_id)
    """
    async with DatabaseManager.get_instance().session() as session:
        yield session


async def get_session_direct() -> AsyncSession:
    """
    Return a raw AsyncSession for dependency-injection frameworks.

    IMPORTANT: The caller is responsible for committing and closing.
    Prefer get_session() (context manager) in all other cases.
    """
    db = DatabaseManager.get_instance()
    if db._session_factory is None:
        raise RuntimeError("DatabaseManager.init() must be awaited before requesting sessions.")
    return db._session_factory()
