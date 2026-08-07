"""Unit-test-level fixtures — all pure Python, no database, no I/O."""

from __future__ import annotations

import pytest

from app.core.result import Failure, NotFound, Success, ValidationError


@pytest.fixture
def success_result():
    """A generic successful Result wrapping an integer."""
    return Success(42)


@pytest.fixture
def failure_result():
    """A generic Failure result."""
    return Failure("test_error", "Something went wrong.")


@pytest.fixture
def not_found_result():
    return NotFound("Resource not found.")


@pytest.fixture
def validation_error_result():
    return ValidationError("must be positive", field="amount")
