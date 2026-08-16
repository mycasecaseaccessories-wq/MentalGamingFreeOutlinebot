"""Backward-compatible database manager import path.

The canonical implementation lives in :mod:`database.connection`; older
integration fixtures and service modules import ``database.db``.
"""
from .connection import DatabaseManager

__all__ = ["DatabaseManager"]
