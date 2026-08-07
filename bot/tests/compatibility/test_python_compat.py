"""Compatibility tests — verify Python version and key dependency contracts."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.unit


class TestPythonVersion:
    def test_python_312_or_higher(self) -> None:
        """The platform requires Python 3.12+."""
        assert sys.version_info >= (3, 12), (
            f"Python 3.12+ required, running {sys.version_info.major}.{sys.version_info.minor}"
        )

    def test_python_not_too_new(self) -> None:
        """Guard against incompatible future Python versions (update when tested)."""
        assert sys.version_info < (3, 15), (
            f"Python {sys.version_info.major}.{sys.version_info.minor} is untested — "
            "update this check after validating compatibility."
        )


class TestCriticalImports:
    """Verify all production dependencies can be imported."""

    def test_telegram_importable(self) -> None:
        import telegram  # noqa: F401

    def test_sqlalchemy_importable(self) -> None:
        import sqlalchemy  # noqa: F401

    def test_pydantic_importable(self) -> None:
        import pydantic  # noqa: F401

    def test_apscheduler_importable(self) -> None:
        import apscheduler  # noqa: F401

    def test_alembic_importable(self) -> None:
        import alembic  # noqa: F401


class TestDependencyVersions:
    """Check that installed dependency versions match expected minimums."""

    def test_pydantic_v2(self) -> None:
        import pydantic

        major = int(pydantic.VERSION.split(".")[0])
        assert major >= 2, f"Pydantic v2+ required, got {pydantic.VERSION}"

    def test_sqlalchemy_v2(self) -> None:
        import sqlalchemy

        major = int(sqlalchemy.__version__.split(".")[0])
        assert major >= 2, f"SQLAlchemy v2+ required, got {sqlalchemy.__version__}"

    def test_python_telegram_bot_v21(self) -> None:
        import telegram

        major = int(telegram.__version__.split(".")[0])
        assert major >= 21, f"python-telegram-bot v21+ required, got {telegram.__version__}"
