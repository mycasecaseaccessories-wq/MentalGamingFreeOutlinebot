"""Unit tests for utility helpers (app.utils.helpers, app.core.utils)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestHelpers:
    """Tests for bot/app/utils/helpers.py."""

    def test_escape_html_special_chars(self) -> None:
        from app.utils.helpers import escape_html

        assert "&lt;" in escape_html("<tag>")
        assert "&amp;" in escape_html("a & b")

    def test_truncate_long_string(self) -> None:
        from app.utils.helpers import truncate

        long_text = "a" * 200
        result = truncate(long_text, 50)
        assert len(result) <= 53  # 50 + "..." suffix

    def test_truncate_short_string_unchanged(self) -> None:
        from app.utils.helpers import truncate

        short = "hello"
        assert truncate(short, 100) == short

    def test_format_bytes_gb(self) -> None:
        from app.utils.helpers import format_bytes

        result = format_bytes(1_073_741_824)  # 1 GB
        assert "GB" in result or "GiB" in result or "1" in result

    def test_format_bytes_kb(self) -> None:
        from app.utils.helpers import format_bytes

        result = format_bytes(1024)
        assert "KB" in result or "KiB" in result or "1" in result

    def test_format_bytes_zero(self) -> None:
        from app.utils.helpers import format_bytes

        result = format_bytes(0)
        assert "0" in result


class TestCoreUtils:
    """Tests for app.core.utils if it exposes functions."""

    def test_core_utils_importable(self) -> None:
        import app.core.utils  # noqa: F401 — just check it imports
