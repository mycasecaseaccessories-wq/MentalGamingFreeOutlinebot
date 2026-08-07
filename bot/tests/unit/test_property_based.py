"""
Property-based tests using Hypothesis.

These tests generate random inputs to find edge cases that hand-written tests miss.
Hypothesis shrinks failing cases to minimal reproducers automatically.
"""

from __future__ import annotations

import string
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.exceptions import ValidationException
from app.core.result import Failure, Success
from app.core.security import generate_otp, mask_secret
from app.core.validators import validate_price, validate_telegram_id

pytestmark = pytest.mark.unit


class TestResultPatternProperties:
    @given(st.integers())
    def test_success_always_succeeds(self, value: int) -> None:
        r = Success(value)
        assert r.is_success
        assert not r.is_failure

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_failure_always_fails(self, code: str, message: str) -> None:
        r = Failure(code, message)
        assert r.is_failure
        assert not r.is_success

    @given(st.integers())
    def test_map_preserves_success(self, value: int) -> None:
        r = Success(value).map(lambda x: x + 1)
        assert r.is_success
        assert r.unwrap() == value + 1

    @given(st.text(min_size=1), st.text(min_size=1))
    def test_map_on_failure_stays_failure(self, code: str, message: str) -> None:
        r = Failure(code, message).map(lambda x: x)  # type: ignore[arg-type]
        assert r.is_failure
        assert r.error.code == code


class TestSecurityProperties:
    @given(st.text(min_size=1, max_size=100))
    def test_mask_secret_never_leaks_full_value(self, secret: str) -> None:
        masked = mask_secret(secret)
        # Masked value must not equal the original secret (unless very short)
        if len(secret) > 8:
            assert masked != secret

    @given(st.integers(min_value=4, max_value=12))
    def test_otp_has_correct_length(self, length: int) -> None:
        otp = generate_otp(length)
        assert len(otp) == length
        assert otp.isdigit()

    @given(st.integers(min_value=4, max_value=12))
    def test_otp_is_numeric(self, length: int) -> None:
        otp = generate_otp(length)
        int(otp)  # must not raise


class TestValidatorProperties:
    @given(st.integers(min_value=1))
    def test_positive_telegram_id_always_valid(self, value: int) -> None:
        result = validate_telegram_id(value)
        assert result == value

    @given(st.integers(max_value=-1))
    def test_negative_telegram_id_valid_for_groups(self, value: int) -> None:
        # Negative IDs are valid for Telegram groups/channels
        result = validate_telegram_id(value)
        assert result == value

    @given(
        st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("99999.99"),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    def test_valid_prices_always_accepted(self, value: Decimal) -> None:
        assume(value > 0)
        result = validate_price(str(value))
        assert result >= Decimal("0.01")

    @given(st.floats(max_value=-0.01, allow_nan=False, allow_infinity=False))
    def test_negative_price_always_rejected(self, value: float) -> None:
        with pytest.raises(ValidationException):
            validate_price(value)
