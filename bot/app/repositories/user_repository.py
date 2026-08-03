"""
UserRepository — compatibility shim.

The full implementation now lives in database/repositories/user_repository.py.
This file exists only for backward compatibility with any import that
still targets app.repositories.user_repository.

Prefer:
    from database.repositories import UserRepository
"""

from database.repositories.user_repository import UserRepository  # noqa: F401

__all__ = ["UserRepository"]
