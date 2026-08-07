"""Custom assertion helpers for the VPN Platform test suite."""

from __future__ import annotations

from typing import Any

from app.core.result import Result


def assert_success(result: Result, expected_value: Any = None) -> None:
    """Assert a Result is successful and optionally check its value."""
    assert result.is_success, (
        f"Expected Success, got Failure: {result.error.code} — {result.error.message}"
        if result.error
        else "Expected Success, got Failure"
    )
    if expected_value is not None:
        assert result.unwrap() == expected_value, (
            f"Expected value {expected_value!r}, got {result.unwrap()!r}"
        )


def assert_failure(result: Result, code: str | None = None) -> None:
    """Assert a Result is a failure and optionally check its error code."""
    assert result.is_failure, (
        f"Expected Failure, got Success with value {result.value!r}"
    )
    if code is not None:
        assert result.error.code == code, (
            f"Expected error code {code!r}, got {result.error.code!r}"
        )


def assert_validation_error(result: Result, field: str | None = None) -> None:
    """Assert a Result is a ValidationError and optionally check the field."""
    assert_failure(result, code="validation_error")
    if field is not None:
        assert result.error.field == field, (
            f"Expected field {field!r}, got {result.error.field!r}"
        )


def assert_not_found(result: Result) -> None:
    """Assert a Result is a NotFound error."""
    assert_failure(result, code="not_found")


def assert_permission_denied(result: Result) -> None:
    """Assert a Result is a permission_denied error."""
    assert_failure(result, code="permission_denied")


def assert_dict_has_keys(d: dict, *keys: str) -> None:
    """Assert a dict contains all the specified keys."""
    missing = [k for k in keys if k not in d]
    assert not missing, f"Dict is missing keys: {missing!r}"


def assert_list_non_empty(lst: list) -> None:
    assert len(lst) > 0, "Expected non-empty list, got empty list"


def assert_list_length(lst: list, expected: int) -> None:
    assert len(lst) == expected, f"Expected list length {expected}, got {len(lst)}"
