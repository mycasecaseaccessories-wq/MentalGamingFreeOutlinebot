"""Unit tests for the custom exception hierarchy (app.core.exceptions)."""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    AppException,
    AuthenticationException,
    CacheException,
    ConfigurationException,
    DatabaseException,
    NotFoundException,
    PaymentException,
    PermissionDeniedException,
    RateLimitException,
    ServerException,
    ValidationException,
    VPNException,
)

pytestmark = pytest.mark.unit


class TestAppException:
    def test_message_and_code(self) -> None:
        exc = AppException("something failed", code="custom_code")
        assert exc.message == "something failed"
        assert exc.code == "custom_code"

    def test_default_code(self) -> None:
        exc = AppException("err")
        assert exc.code == "app_error"

    def test_default_http_status(self) -> None:
        exc = AppException("err")
        assert exc.http_status == 500

    def test_to_dict_shape(self) -> None:
        d = AppException("err", code="app_error", details={"k": "v"}).to_dict()
        assert d["error"] == "app_error"
        assert d["message"] == "err"
        assert d["details"] == {"k": "v"}

    def test_is_exception(self) -> None:
        with pytest.raises(AppException):
            raise AppException("boom")


class TestValidationException:
    def test_code(self) -> None:
        exc = ValidationException("price", "must be positive")
        assert exc.code == "validation_error"

    def test_http_status(self) -> None:
        exc = ValidationException("field", "reason")
        assert exc.http_status == 422

    def test_details_contain_field_and_reason(self) -> None:
        exc = ValidationException("email", "invalid format", value="not@valid")
        assert exc.details["field"] == "email"
        assert exc.details["reason"] == "invalid format"

    def test_inherits_app_exception(self) -> None:
        exc = ValidationException("x", "y")
        assert isinstance(exc, AppException)


class TestAuthenticationException:
    def test_code(self) -> None:
        exc = AuthenticationException()
        assert exc.code == "authentication_failed"
        assert exc.http_status == 401


class TestPermissionDeniedException:
    def test_code(self) -> None:
        exc = PermissionDeniedException("manage_users")
        assert exc.code == "permission_denied"
        assert exc.http_status == 403

    def test_required_permission_in_details(self) -> None:
        exc = PermissionDeniedException("manage_users")
        assert exc.details["required"] == "manage_users"

    def test_empty_permission_message(self) -> None:
        exc = PermissionDeniedException()
        assert "do not have permission" in exc.message.lower()


class TestNotFoundException:
    def test_code_contains_resource(self) -> None:
        exc = NotFoundException("user", 42)
        assert "user" in exc.code

    def test_message_contains_resource(self) -> None:
        exc = NotFoundException("package", "uuid-123")
        assert "package" in exc.message.lower()

    def test_http_status(self) -> None:
        assert NotFoundException("item").http_status == 404


class TestRateLimitException:
    def test_code(self) -> None:
        exc = RateLimitException(retry_after=30)
        assert exc.code == "rate_limit_exceeded"
        assert exc.http_status == 429

    def test_retry_after_attribute(self) -> None:
        exc = RateLimitException(retry_after=60)
        assert exc.retry_after == 60


class TestConfigurationException:
    def test_code_and_setting(self) -> None:
        exc = ConfigurationException("BOT_TOKEN", "is missing")
        assert exc.code == "configuration_error"
        assert exc.setting == "BOT_TOKEN"


class TestDatabaseException:
    def test_code(self) -> None:
        exc = DatabaseException("insert failed", operation="insert", table="users")
        assert exc.code == "database_error"
        assert exc.http_status == 503

    def test_operation_and_table(self) -> None:
        exc = DatabaseException("err", operation="select", table="orders")
        assert exc.operation == "select"
        assert exc.table == "orders"


class TestServerException:
    def test_code(self) -> None:
        exc = ServerException("API timeout", server_id=1)
        assert exc.code == "server_error"
        assert exc.server_id == 1


class TestVPNException:
    def test_code(self) -> None:
        exc = VPNException("key creation failed", key_id="vpn-key-1")
        assert exc.code == "vpn_error"


class TestPaymentException:
    def test_code_and_status(self) -> None:
        exc = PaymentException("insufficient funds", order_id=99, method="wallet")
        assert exc.code == "payment_error"
        assert exc.http_status == 402
        assert exc.order_id == 99
        assert exc.method == "wallet"


class TestExceptionHierarchy:
    def test_all_subclass_app_exception(self) -> None:
        subclasses = [
            ValidationException("f", "r"),
            AuthenticationException(),
            PermissionDeniedException(),
            NotFoundException("x"),
            RateLimitException(),
            ConfigurationException("x"),
            DatabaseException("msg"),
            CacheException(),
            ServerException("msg"),
            VPNException("msg"),
            PaymentException("msg"),
        ]
        for exc in subclasses:
            assert isinstance(exc, AppException), f"{type(exc)} is not AppException subclass"
