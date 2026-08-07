"""Mock database — captures calls without touching real SQLite/PostgreSQL."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class MockDatabaseManager:
    """Mock for database.db.DatabaseManager."""

    def __init__(self) -> None:
        self.init = AsyncMock()
        self.close = AsyncMock()
        self.session = MagicMock()
        self._initialized = True

    def get_session(self) -> Any:
        """Return a mock async context-manager session."""
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        session.scalars = AsyncMock()
        session.add = MagicMock()
        session.delete = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        return session


class MockRepository:
    """Generic mock repository for unit testing services."""

    def __init__(self) -> None:
        self.get_by_id = AsyncMock(return_value=None)
        self.get_all = AsyncMock(return_value=[])
        self.create = AsyncMock()
        self.update = AsyncMock()
        self.delete = AsyncMock()
        self.exists = AsyncMock(return_value=False)
        self.count = AsyncMock(return_value=0)
