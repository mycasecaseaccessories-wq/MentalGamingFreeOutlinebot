"""Integration-test-level fixtures — use in-memory SQLite for isolation."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from app.core.result import Success


@pytest_asyncio.fixture
async def db_manager():
    """
    Spin up an in-memory async SQLite database for a single test.

    Creates all tables via the ORM metadata, yields the DatabaseManager,
    then tears it down.  Tests that modify data get a clean slate each run.
    """
    from database.db import DatabaseManager

    mgr = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await mgr.init()
    yield mgr
    await mgr.close()


@pytest_asyncio.fixture
async def service_registry(db_manager):
    """ServiceRegistry wired to the in-memory test database."""
    from app.services.registry import ServiceRegistry

    registry = ServiceRegistry(db_manager)
    registry.initialise_all()
    return registry
