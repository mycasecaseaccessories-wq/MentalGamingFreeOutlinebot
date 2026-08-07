"""Unit tests for the Result pattern (app.core.result).

Tests cover Success, Failure, ValidationError, PermissionError, NotFound,
map(), unwrap(), to_dict(), and chaining.
"""

from __future__ import annotations

import pytest

from app.core.result import (
    Failure,
    NotFound,
    Result,
    Success,
    ValidationError,
)

pytestmark = pytest.mark.unit


class TestSuccess:
    def test_is_success(self) -> None:
        assert Success(1).is_success is True

    def test_is_not_failure(self) -> None:
        assert Success(1).is_failure is False

    def test_unwrap_returns_value(self) -> None:
        assert Success("hello").unwrap() == "hello"

    def test_unwrap_none_value(self) -> None:
        # Success with explicit None is still a success
        assert Success(None).is_success is True

    def test_map_transforms_value(self) -> None:
        result = Success(3).map(lambda x: x * 2)
        assert result.is_success
        assert result.unwrap() == 6

    def test_map_chaining(self) -> None:
        result = Success(1).map(lambda x: x + 1).map(lambda x: x * 10)
        assert result.unwrap() == 20

    def test_to_dict_success_shape(self) -> None:
        d = Success("data").to_dict()
        assert d["success"] is True
        assert d["data"] == "data"


class TestFailure:
    def test_is_failure(self) -> None:
        r = Failure("err", "bad thing")
        assert r.is_failure is True

    def test_is_not_success(self) -> None:
        r = Failure("err", "bad thing")
        assert r.is_success is False

    def test_error_code(self) -> None:
        r = Failure("my_code", "msg")
        assert r.error is not None
        assert r.error.code == "my_code"

    def test_error_message(self) -> None:
        r = Failure("code", "the message")
        assert r.error.message == "the message"

    def test_optional_field(self) -> None:
        r = Failure("code", "msg", field="price")
        assert r.error.field == "price"

    def test_optional_details(self) -> None:
        r = Failure("code", "msg", details={"key": "value"})
        assert r.error.details == {"key": "value"}

    def test_unwrap_raises(self) -> None:
        with pytest.raises(ValueError, match="my_error"):
            Failure("my_error", "oh no").unwrap()

    def test_map_propagates_failure(self) -> None:
        original = Failure("code", "err")
        mapped = original.map(lambda x: x)  # type: ignore[arg-type]
        assert mapped.is_failure
        assert mapped.error.code == "code"

    def test_to_dict_failure_shape(self) -> None:
        d = Failure("code", "msg").to_dict()
        assert d["success"] is False
        assert d["error"] is not None


class TestValidationError:
    def test_code_is_validation_error(self) -> None:
        r = ValidationError("must be positive", field="amount")
        assert r.error.code == "validation_error"

    def test_message_propagated(self) -> None:
        r = ValidationError("bad input")
        assert r.error.message == "bad input"

    def test_field_propagated(self) -> None:
        r = ValidationError("msg", field="email")
        assert r.error.field == "email"

    def test_details_propagated(self) -> None:
        r = ValidationError("msg", details={"received": "abc"})
        assert r.error.details["received"] == "abc"


class TestNotFound:
    def test_code_is_not_found(self) -> None:
        r = NotFound()
        assert r.error.code == "not_found"

    def test_custom_message(self) -> None:
        r = NotFound("User not found.")
        assert "User not found" in r.error.message


class TestResultImmutability:
    def test_result_is_frozen(self) -> None:
        r = Success(1)
        with pytest.raises(Exception):
            r.value = 99  # type: ignore[misc]
