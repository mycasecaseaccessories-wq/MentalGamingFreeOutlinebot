"""Unit tests for security utilities (app.core.security)."""

from __future__ import annotations

import pytest

from app.core.security import (
    generate_otp,
    generate_referral_code,
    generate_token,
    hash_value,
    hmac_sign,
    hmac_verify,
    mask_database_url,
    mask_secret,
    mask_token,
    redact_sensitive,
    sanitize_html,
    sanitize_text,
    strip_control_chars,
)

pytestmark = pytest.mark.unit


class TestMaskSecret:
    def test_short_secret_fully_masked(self) -> None:
        result = mask_secret("ab")
        assert "*" in result

    def test_long_secret_partially_visible(self) -> None:
        secret = "1234567890abcdef"
        masked = mask_secret(secret)
        assert masked != secret
        assert "*" in masked
        assert len(masked) >= 4

    def test_empty_string_returns_empty(self) -> None:
        assert mask_secret("") == ""

    def test_does_not_expose_full_value(self) -> None:
        secret = "super_secret_token_value_here"
        masked = mask_secret(secret)
        assert secret not in masked


class TestMaskToken:
    def test_shows_first_8_chars(self) -> None:
        token = "abcdefgh1234567890"
        masked = mask_token(token)
        assert masked.startswith("abcdefgh")

    def test_masks_remainder(self) -> None:
        token = "abcdefgh1234567890"
        masked = mask_token(token)
        assert "12345" not in masked


class TestMaskDatabaseUrl:
    def test_credentials_removed(self) -> None:
        url = "postgresql+asyncpg://user:secret@host:5432/db"
        masked = mask_database_url(url)
        assert "secret" not in masked
        assert "***@" in masked

    def test_url_without_credentials_unchanged(self) -> None:
        url = "sqlite:///./data/mental_vpn.db"
        # No credentials to mask — returned as-is
        assert mask_database_url(url) == url


class TestRedactSensitive:
    def test_redacts_bot_token_pattern(self) -> None:
        text = "token=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        redacted = redact_sensitive(text)
        assert "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij" not in redacted

    def test_redacts_password_pattern(self) -> None:
        text = "password=mysupersecretpassword"
        redacted = redact_sensitive(text)
        assert "mysupersecretpassword" not in redacted
        assert "***" in redacted

    def test_plain_text_unaffected(self) -> None:
        text = "This is a normal log message with no secrets."
        assert redact_sensitive(text) == text


class TestSanitizeHtml:
    def test_escapes_html_chars(self) -> None:
        result = sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;" in result

    def test_escapes_ampersand(self) -> None:
        assert "&amp;" in sanitize_html("a & b")

    def test_safe_text_unchanged(self) -> None:
        assert sanitize_html("Hello World") == "Hello World"


class TestSanitizeText:
    def test_strips_leading_trailing_whitespace(self) -> None:
        assert sanitize_text("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self) -> None:
        assert sanitize_text("hello   world") == "hello world"

    def test_truncates_to_max_length(self) -> None:
        text = "a" * 5000
        result = sanitize_text(text, max_length=100)
        assert len(result) == 100


class TestStripControlChars:
    def test_removes_null_bytes(self) -> None:
        assert "\x00" not in strip_control_chars("hello\x00world")

    def test_preserves_newlines_and_tabs(self) -> None:
        text = "line1\nline2\ttabbed"
        result = strip_control_chars(text)
        assert "\n" in result
        assert "\t" in result


class TestGenerateToken:
    def test_returns_string(self) -> None:
        assert isinstance(generate_token(), str)

    def test_minimum_length(self) -> None:
        token = generate_token(32)
        assert len(token) >= 32

    def test_tokens_are_unique(self) -> None:
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100


class TestGenerateOtp:
    def test_returns_numeric_string(self) -> None:
        otp = generate_otp(6)
        assert otp.isdigit()

    def test_correct_length(self) -> None:
        for length in [4, 6, 8]:
            assert len(generate_otp(length)) == length

    def test_zero_padded(self) -> None:
        # OTPs must be zero-padded
        # Repeatedly generate until we see a leading-zero case statistically
        otps = [generate_otp(6) for _ in range(1000)]
        assert all(len(o) == 6 for o in otps)


class TestGenerateReferralCode:
    def test_correct_length(self) -> None:
        assert len(generate_referral_code(8)) == 8

    def test_no_ambiguous_chars(self) -> None:
        for _ in range(200):
            code = generate_referral_code(8)
            for char in "0OIl1":
                assert char not in code

    def test_uppercase_only(self) -> None:
        code = generate_referral_code(8)
        assert code == code.upper()


class TestHashValue:
    def test_same_input_same_hash(self) -> None:
        assert hash_value("password") == hash_value("password")

    def test_different_input_different_hash(self) -> None:
        assert hash_value("password1") != hash_value("password2")

    def test_salt_changes_hash(self) -> None:
        assert hash_value("pass", "salt1") != hash_value("pass", "salt2")

    def test_returns_hex_string(self) -> None:
        result = hash_value("value")
        assert all(c in "0123456789abcdef" for c in result)


class TestHmac:
    def test_sign_and_verify(self) -> None:
        sig = hmac_sign("message", "secret")
        assert hmac_verify("message", sig, "secret")

    def test_wrong_secret_fails(self) -> None:
        sig = hmac_sign("message", "secret")
        assert not hmac_verify("message", sig, "wrong_secret")

    def test_tampered_message_fails(self) -> None:
        sig = hmac_sign("original", "secret")
        assert not hmac_verify("tampered", sig, "secret")

    def test_signature_is_hex_string(self) -> None:
        sig = hmac_sign("msg", "key")
        assert all(c in "0123456789abcdef" for c in sig)
