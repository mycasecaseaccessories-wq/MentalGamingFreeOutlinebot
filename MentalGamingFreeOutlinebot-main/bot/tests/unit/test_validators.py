"""Unit tests for input validators (app.core.validators)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.exceptions import ValidationException
from app.core.validators import (
    validate_duration_days,
    validate_email,
    validate_gb,
    validate_json,
    validate_positive_int,
    validate_price,
    validate_telegram_id,
    validate_url,
    validate_username,
    validate_uuid,
)

pytestmark = pytest.mark.unit


class TestValidateTelegramId:
    def test_valid_positive_id(self) -> None:
        assert validate_telegram_id(123456789) == 123456789

    def test_valid_negative_id(self) -> None:
        # Group/channel IDs can be negative
        assert validate_telegram_id(-100123456789) == -100123456789

    def test_string_input_converted(self) -> None:
        assert validate_telegram_id("999") == 999

    def test_zero_raises(self) -> None:
        with pytest.raises(ValidationException, match="zero"):
            validate_telegram_id(0)

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_telegram_id("abc")

    def test_none_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_telegram_id(None)


class TestValidateUsername:
    def test_valid_username(self) -> None:
        assert validate_username("john_doe") == "john_doe"

    def test_strips_at_prefix(self) -> None:
        assert validate_username("@john_doe") == "john_doe"

    def test_returns_none_for_empty(self) -> None:
        assert validate_username("") is None
        assert validate_username(None) is None

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_username("abc")

    def test_special_chars_raise(self) -> None:
        with pytest.raises(ValidationException):
            validate_username("user name!")


class TestValidatePrice:
    def test_valid_decimal(self) -> None:
        assert validate_price("12.50") == Decimal("12.50")

    def test_integer_accepted(self) -> None:
        assert validate_price(10) == Decimal("10.00")

    def test_zero_raises_by_default(self) -> None:
        with pytest.raises(ValidationException, match="zero"):
            validate_price(0)

    def test_zero_allowed_when_flag_set(self) -> None:
        assert validate_price(0, allow_zero=True) == Decimal("0.00")

    def test_negative_raises(self) -> None:
        with pytest.raises(ValidationException, match="negative"):
            validate_price(-1)

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_price("abc")


class TestValidateGb:
    def test_valid_float(self) -> None:
        assert validate_gb(10.5) == 10.5

    def test_zero_allowed_by_default(self) -> None:
        assert validate_gb(0) == 0.0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValidationException, match="negative"):
            validate_gb(-1)

    def test_string_input_accepted(self) -> None:
        assert validate_gb("5.0") == 5.0


class TestValidateDurationDays:
    def test_valid_duration(self) -> None:
        assert validate_duration_days(30) == 30

    def test_one_day_is_valid(self) -> None:
        assert validate_duration_days(1) == 1

    def test_max_days(self) -> None:
        assert validate_duration_days(3650) == 3650

    def test_zero_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_duration_days(0)

    def test_exceeds_max_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_duration_days(3651)

    def test_float_truncated_to_int(self) -> None:
        assert validate_duration_days(30.9) == 30


class TestValidateEmail:
    def test_valid_email(self) -> None:
        assert validate_email("user@example.com") == "user@example.com"

    def test_uppercased_email_lowercased(self) -> None:
        assert validate_email("USER@EXAMPLE.COM") == "user@example.com"

    def test_invalid_email_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_email("not_an_email")

    def test_missing_domain_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_email("user@")


class TestValidateUrl:
    def test_valid_https_url(self) -> None:
        url = "https://example.com/path"
        assert validate_url(url) == url

    def test_valid_http_url(self) -> None:
        url = "http://localhost:8080"
        assert validate_url(url) == url

    def test_ftp_raises_by_default(self) -> None:
        with pytest.raises(ValidationException):
            validate_url("ftp://files.example.com")

    def test_custom_schemes(self) -> None:
        assert validate_url("ftp://files.example.com", schemes=("ftp",))


class TestValidateUuid:
    def test_valid_uuid(self) -> None:
        result = validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_uppercase_normalized(self) -> None:
        result = validate_uuid("550E8400-E29B-41D4-A716-446655440000")
        assert result == result.lower()

    def test_invalid_uuid_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_uuid("not-a-uuid")


class TestValidateJson:
    def test_valid_json_object(self) -> None:
        result = validate_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_array(self) -> None:
        result = validate_json("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_json("{not valid json}")


class TestValidatePositiveInt:
    def test_valid_positive(self) -> None:
        assert validate_positive_int("count", 5) == 5

    def test_zero_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_positive_int("count", 0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValidationException):
            validate_positive_int("count", -1)

    def test_max_value_enforced(self) -> None:
        with pytest.raises(ValidationException):
            validate_positive_int("count", 1000, max_value=100)

    def test_at_max_value_passes(self) -> None:
        assert validate_positive_int("count", 100, max_value=100) == 100
