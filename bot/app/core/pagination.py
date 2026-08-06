"""Reusable pagination, filtering, sorting, and searching primitives.

These models describe transport-level query options only.  Repositories remain
responsible for translating them into safe SQL expressions.
"""

from __future__ import annotations

from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Validated page/query options shared by repositories and future APIs."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: Optional[str] = Field(default=None, max_length=256)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort_by: Optional[str] = Field(default=None, max_length=64)
    sort_direction: Literal["asc", "desc"] = "asc"

    @property
    def offset(self) -> int:
        """Return the zero-based offset for a database query."""
        return (self.page - 1) * self.page_size


class PaginationMeta(BaseModel):
    """Metadata returned with a paginated collection."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(default=0, ge=0)

    @property
    def total_pages(self) -> int:
        """Return the number of pages, including zero for an empty result."""
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1 and self.total > 0


class PaginatedResult(BaseModel, Generic[T]):
    """Generic collection envelope for service/repository boundaries."""

    items: list[T] = Field(default_factory=list)
    meta: PaginationMeta


# Public aliases used by API adapters without breaking the original names.
PaginationRequest = PaginationParams
PaginationResponse = PaginatedResult


class PageInfo(BaseModel):
    has_next_page: bool = False
    has_previous_page: bool = False
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None


class CursorPagination(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    after: Optional[str] = None
    before: Optional[str] = None

    @property
    def direction(self) -> str:
        return "before" if self.before else "after"