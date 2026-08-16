"""
BaseRepository — compatibility shim.

The full implementation now lives in database/repositories/base.py.
This file exists only for backward compatibility.

Prefer:
    from database.repositories import BaseRepository
"""

from database.repositories.base import BaseRepository  # noqa: F401

__all__ = ["BaseRepository"]
