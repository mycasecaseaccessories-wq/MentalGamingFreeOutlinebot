"""
Generic async repository base class.

All concrete repositories extend BaseRepository[ModelT, DomainT] to
inherit standard CRUD scaffolding.  Override any method to provide
entity-specific behaviour.

Type parameters
---------------
ModelT   The SQLAlchemy ORM mapped class (e.g. UserORM).
DomainT  The domain model class returned to callers (e.g. User).
"""

from __future__ import annotations

import logging
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import BaseModel

ModelT  = TypeVar("ModelT",  bound=BaseModel)
DomainT = TypeVar("DomainT")


class BaseRepository(Generic[ModelT, DomainT]):
    """
    Generic CRUD repository with async SQLAlchemy session support.

    Concrete subclasses MUST set:
        orm_class    — the SQLAlchemy mapped class.
        domain_class — the domain model class (may differ from orm_class).

    Subclasses MAY override _to_domain() to customise ORM → domain mapping.

    Usage:
        class UserRepository(BaseRepository[UserORM, User]):
            orm_class    = UserORM
            domain_class = User

            def _to_domain(self, row: UserORM) -> User:
                return User(telegram_id=row.telegram_id, ...)
    """

    orm_class:    Type[ModelT]  = NotImplemented  # type: ignore[assignment]
    domain_class: Type[DomainT] = NotImplemented  # type: ignore[assignment]

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialise with an injected async session.

        Args:
            session: AsyncSession obtained from get_session() or db.session().
        """
        self._session = session
        self._log = logging.getLogger(f"repositories.{self.__class__.__name__}")

    # ── Mapping ────────────────────────────────────────────────────────────

    def _to_domain(self, row: ModelT) -> DomainT:
        """
        Convert an ORM row to a domain model instance.

        The default implementation passes the ORM object through unchanged.
        Override this in concrete repositories to return proper domain objects.
        """
        return row  # type: ignore[return-value]

    # ── CRUD ───────────────────────────────────────────────────────────────

    async def get_by_id(self, record_id: int) -> Optional[DomainT]:
        """
        Fetch a single record by its primary key.

        Returns:
            Domain model instance, or None when not found.
        """
        row = await self._session.get(self.orm_class, record_id)
        return self._to_domain(row) if row is not None else None

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[DomainT]:
        """
        Fetch a paginated list of all records ordered by id ascending.

        Args:
            limit:  Maximum number of records to return (default 100).
            offset: Number of records to skip for pagination.
        """
        stmt = (
            select(self.orm_class)
            .order_by(self.orm_class.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def create(self, **kwargs: Any) -> DomainT:
        """
        Persist a new record and return the domain model.

        Args:
            **kwargs: Column values for the new record.

        Returns:
            The newly created domain model with id and timestamps populated.
        """
        row = self.orm_class(**kwargs)
        self._session.add(row)
        await self._session.flush()   # Populate id without committing.
        await self._session.refresh(row)
        self._log.debug("created %s id=%s", self.orm_class.__tablename__, row.id)
        return self._to_domain(row)

    async def update(self, record_id: int, **kwargs: Any) -> Optional[DomainT]:
        """
        Update fields on an existing record.

        Args:
            record_id: Primary key of the record to update.
            **kwargs:  Column names and new values.

        Returns:
            Updated domain model, or None when the record is not found.
        """
        row = await self._session.get(self.orm_class, record_id)
        if row is None:
            return None
        for key, value in kwargs.items():
            setattr(row, key, value)
        await self._session.flush()
        await self._session.refresh(row)
        self._log.debug("updated %s id=%s", self.orm_class.__tablename__, record_id)
        return self._to_domain(row)

    async def delete(self, record_id: int) -> bool:
        """
        Hard-delete a record by its primary key.

        Returns:
            True if a record was found and deleted, False otherwise.
        """
        row = await self._session.get(self.orm_class, record_id)
        if row is None:
            return False
        await self._session.delete(row)
        self._log.debug("deleted %s id=%s", self.orm_class.__tablename__, record_id)
        return True

    async def count(self) -> int:
        """Return the total number of records in the table."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self.orm_class)
        result = await self._session.execute(stmt)
        return result.scalar_one()
