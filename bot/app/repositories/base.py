"""
Base repository.

Provides generic CRUD operations that concrete repositories can inherit
and optionally override.

Type parameter T: the domain model class this repository manages.
"""

from __future__ import annotations

import logging
from typing import Generic, List, Optional, Type, TypeVar

from database.connection import DatabaseManager

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Generic CRUD repository.

    Concrete repositories should subclass this and set `model_class`
    to the corresponding ORM model, and `domain_class` to the domain model.

    Example:
        class UserRepository(BaseRepository[User]):
            model_class = UserORM
            domain_class = User
    """

    model_class: Type  = NotImplemented  # ORM model (SQLAlchemy mapped class)
    domain_class: Type = NotImplemented  # Domain model returned to callers

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db: DatabaseManager = db or DatabaseManager.get_instance()
        self.logger: logging.Logger = logging.getLogger(
            f"repositories.{self.__class__.__name__}"
        )

    async def get_by_id(self, record_id: int) -> Optional[T]:
        """
        Fetch a single record by its primary key.

        Returns:
            Domain model instance, or None if not found.
        """
        # TODO (Phase 1): implement with SQLAlchemy async session
        raise NotImplementedError(f"{self.__class__.__name__}.get_by_id")

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Fetch a paginated list of all records.

        Args:
            limit:  Maximum number of records to return.
            offset: Number of records to skip (for pagination).
        """
        # TODO (Phase 1): implement with SQLAlchemy async session
        raise NotImplementedError(f"{self.__class__.__name__}.list_all")

    async def create(self, **kwargs) -> T:
        """
        Persist a new record and return the domain model.

        Args:
            **kwargs: Column values for the new record.
        """
        # TODO (Phase 1): implement with SQLAlchemy async session
        raise NotImplementedError(f"{self.__class__.__name__}.create")

    async def update(self, record_id: int, **kwargs) -> Optional[T]:
        """
        Update an existing record and return the updated domain model.

        Args:
            record_id: Primary key of the record to update.
            **kwargs:  Column values to update.
        """
        # TODO (Phase 1): implement with SQLAlchemy async session
        raise NotImplementedError(f"{self.__class__.__name__}.update")

    async def delete(self, record_id: int) -> bool:
        """
        Hard-delete a record by its primary key.

        Returns:
            True if a record was deleted, False if not found.
        """
        # TODO (Phase 1): implement with SQLAlchemy async session
        raise NotImplementedError(f"{self.__class__.__name__}.delete")
