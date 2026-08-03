"""
ORM declarative base + reusable BaseModel mixin.

All SQLAlchemy mapped model classes MUST inherit from BaseModel (not Base
directly). This guarantees every table has the standard id / created_at /
updated_at columns and that Base.metadata.create_all() in DatabaseManager
discovers every table.

Usage:
    from database.base import BaseModel
    from sqlalchemy.orm import Mapped, mapped_column
    from sqlalchemy import String

    class UserORM(BaseModel):
        __tablename__ = "users"
        telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
        full_name: Mapped[str] = mapped_column(String(255))
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """
    Declarative base for SQLAlchemy 2.x.

    Do not inherit from this directly — use BaseModel instead so every
    table gets the standard primary key and audit timestamps.
    """


class BaseModel(Base):
    """
    Abstract base model inherited by every ORM table in the platform.

    Columns
    -------
    id          Auto-incrementing integer primary key.
    created_at  UTC timestamp set once on INSERT.
    updated_at  UTC timestamp updated automatically on every UPDATE.
                (Updated in Python; set onupdate for DB-level enforcement.)
    """

    __abstract__ = True  # SQLAlchemy will NOT create a table for this class.

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Auto-incrementing primary key",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
        comment="UTC timestamp of record creation",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
        comment="UTC timestamp of last record update",
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"
