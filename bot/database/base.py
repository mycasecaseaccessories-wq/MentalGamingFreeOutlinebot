"""
ORM declarative base.

All SQLAlchemy mapped model classes MUST inherit from Base defined here.
This ensures that Base.metadata.create_all() in DatabaseManager.init()
discovers every table across the application.

Usage:
    from database.base import Base
    from sqlalchemy import Column, Integer, String

    class UserORM(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        ...

NOTE: ORM model classes will be added in Phase 1 (UserORM) and beyond.
      This file is intentionally minimal — it only provides the Base.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.

    Inheriting from DeclarativeBase (SQLAlchemy 2.x style) rather than
    the legacy declarative_base() function provides better type inference.
    """
