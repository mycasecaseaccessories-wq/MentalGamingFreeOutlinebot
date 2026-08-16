"""Unit tests for pagination utilities (app.core.pagination)."""

from __future__ import annotations

import pytest

from app.core.pagination import CursorPagination, PageInfo

pytestmark = pytest.mark.unit


class TestCursorPagination:
    def test_direction_after(self) -> None:
        cursor = CursorPagination(limit=10, after="cursor-1")
        assert cursor.direction == "after"

    def test_direction_before(self) -> None:
        cursor = CursorPagination(limit=10, before="cursor-2")
        assert cursor.direction == "before"

    def test_direction_first_when_no_cursor(self) -> None:
        cursor = CursorPagination(limit=10)
        assert cursor.direction == "first"

    def test_limit_respected(self) -> None:
        cursor = CursorPagination(limit=25)
        assert cursor.limit == 25

    def test_default_limit(self) -> None:
        cursor = CursorPagination()
        assert cursor.limit >= 1


class TestPageInfo:
    def test_has_next_page(self) -> None:
        info = PageInfo(has_next_page=True, next_cursor="abc")
        assert info.has_next_page is True
        assert info.next_cursor == "abc"

    def test_no_next_page(self) -> None:
        info = PageInfo(has_next_page=False)
        assert info.has_next_page is False

    def test_total_count(self) -> None:
        info = PageInfo(has_next_page=False, total_count=42)
        assert info.total_count == 42
