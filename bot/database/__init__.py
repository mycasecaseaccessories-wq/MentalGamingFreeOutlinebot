"""
Database package.

Manages async database connectivity for the platform.

Design decisions:
  • SQLAlchemy 2.x async engine is used for both SQLite (dev) and
    PostgreSQL (production) — the switch is transparent to the rest of the app.
  • All database access goes through async sessions obtained via
    DatabaseManager.session().
  • The ORM base class (Base) is defined in database/base.py; all mapped
    models must inherit from it.

Initialisation (in main.py):
    from database import DatabaseManager
    await DatabaseManager.get_instance().init()
"""

from .connection import DatabaseManager
from .base import Base

__all__ = ["DatabaseManager", "Base"]
