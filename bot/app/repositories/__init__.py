"""
Repositories package.

Implements the Repository pattern — each repository wraps all database
access for a single aggregate root (entity family).

Rules:
  • Repositories MUST NOT contain business logic.
  • Repositories MUST return domain model objects, not raw ORM rows.
  • Services MUST NOT write SQL directly; they call repository methods.

Current repositories:
    UserRepository  — CRUD for User records.
"""

from .user_repository import UserRepository

__all__ = ["UserRepository"]
