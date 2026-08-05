"""
Custom exception hierarchy.

Every module in the platform must raise one of these exceptions rather
than bare ``Exception`` or built-in exceptions.  This makes error handling
predictable: callers catch ``AppException`` to handle any platform error,
or a specific subclass for targeted handling.

Hierarchy
---------
AppException
├── ValidationException
├── AuthenticationException
├── PermissionDeniedException
├── ConfigurationException
├── DatabaseException
├── CacheException
├── NotFoundException
├── RateLimitException
├── ServerException        (Outline API / VPN server errors)
├── VPNException
└── PaymentException

Usage
-----
    from app.core.exceptions import NotFoundException, ValidationException

    raise NotFoundException("user", telegram_id)
    raise ValidationException("price", "must be positive", value=price)
"""

from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# Root exception
# ---------------------------------------------------------------------------

class AppException(Exception):
    """
    Root exception for all platform errors.

    Attributes:
        message    Human-readable error description.
        code       Short machine-readable error code (e.g. "user_not_found").
        details    Optional dict with structured context for logging/APIs.
        http_status HTTP status code hint for future REST API responses.
    """

    default_code: str = "app_error"
    default_http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details: dict[str, Any] = details or {}
        self.http_status = http_status or self.default_http_status

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (for API responses and logging)."""
        return {
            "error":   self.code,
            "message": self.message,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Input / validation errors  (4xx range)
# ---------------------------------------------------------------------------

class ValidationException(AppException):
    """
    Raised when input data fails validation.

    Args:
        field:   Name of the invalid field.
        reason:  Human-readable reason for failure.
        value:   The rejected value (excluded from user-facing messages).
    """

    default_code = "validation_error"
    default_http_status = 422

    def __init__(
        self,
        field: str,
        reason: str,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"Validation failed for '{field}': {reason}",
            code="validation_error",
            details={"field": field, "reason": reason, "value": repr(value)},
            **kwargs,
        )
        self.field = field
        self.reason = reason
        self.value = value


class AuthenticationException(AppException):
    """
    Raised when a user cannot be authenticated (missing/invalid identity).
    """
    default_code = "authentication_failed"
    default_http_status = 401

    def __init__(self, message: str = "Authentication required.", **kwargs: Any) -> None:
        super().__init__(message, code="authentication_failed", **kwargs)


class PermissionDeniedException(AppException):
    """
    Raised when a user lacks the required permission for an action.

    Args:
        required_permission: The permission that was missing.
    """
    default_code = "permission_denied"
    default_http_status = 403

    def __init__(
        self,
        required_permission: str = "",
        message: str = "",
        **kwargs: Any,
    ) -> None:
        msg = message or (
            f"Permission denied: '{required_permission}' is required."
            if required_permission else "You do not have permission to perform this action."
        )
        super().__init__(
            msg,
            code="permission_denied",
            details={"required": required_permission},
            **kwargs,
        )
        self.required_permission = required_permission


class NotFoundException(AppException):
    """
    Raised when a requested resource does not exist.

    Args:
        resource: Resource type (e.g. "user", "package", "vpn_key").
        identifier: The ID or key that was looked up.
    """
    default_code = "not_found"
    default_http_status = 404

    def __init__(self, resource: str, identifier: Any = None, **kwargs: Any) -> None:
        id_str = f" '{identifier}'" if identifier is not None else ""
        super().__init__(
            f"{resource.capitalize()}{id_str} not found.",
            code=f"{resource}_not_found",
            details={"resource": resource, "identifier": str(identifier)},
            **kwargs,
        )
        self.resource = resource
        self.identifier = identifier


class RateLimitException(AppException):
    """
    Raised when a user or IP exceeds an allowed request rate.

    Args:
        retry_after: Seconds until the limit resets (0 if unknown).
    """
    default_code = "rate_limit_exceeded"
    default_http_status = 429

    def __init__(self, retry_after: int = 0, **kwargs: Any) -> None:
        super().__init__(
            "Rate limit exceeded. Please try again later.",
            code="rate_limit_exceeded",
            details={"retry_after": retry_after},
            **kwargs,
        )
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Infrastructure errors  (5xx range)
# ---------------------------------------------------------------------------

class ConfigurationException(AppException):
    """
    Raised when required configuration values are missing or invalid.

    Args:
        setting: Name of the misconfigured setting or env var.
    """
    default_code = "configuration_error"
    default_http_status = 500

    def __init__(self, setting: str, reason: str = "", **kwargs: Any) -> None:
        msg = f"Configuration error for '{setting}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, code="configuration_error",
                         details={"setting": setting, "reason": reason}, **kwargs)
        self.setting = setting


class DatabaseException(AppException):
    """
    Raised when a database operation fails (connection, query, constraint).

    Args:
        operation: SQL operation that failed (e.g. "insert", "select").
        table:     Table or entity involved.
    """
    default_code = "database_error"
    default_http_status = 503

    def __init__(
        self,
        message: str,
        operation: str = "",
        table: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code="database_error",
            details={"operation": operation, "table": table},
            **kwargs,
        )
        self.operation = operation
        self.table = table


class CacheException(AppException):
    """Raised when a cache operation fails."""
    default_code = "cache_error"
    default_http_status = 503

    def __init__(self, message: str = "Cache operation failed.", **kwargs: Any) -> None:
        super().__init__(message, code="cache_error", **kwargs)


class ServerException(AppException):
    """
    Raised when an Outline VPN server API call fails.

    Args:
        server_id: Database ID of the server involved.
    """
    default_code = "server_error"
    default_http_status = 503

    def __init__(self, message: str, server_id: Any = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code="server_error",
            details={"server_id": str(server_id)},
            **kwargs,
        )
        self.server_id = server_id


class VPNException(AppException):
    """
    Raised when a VPN key operation fails (create, revoke, sync).

    Args:
        key_id: The affected VPN key ID (if known).
    """
    default_code = "vpn_error"
    default_http_status = 503

    def __init__(self, message: str, key_id: Any = None, **kwargs: Any) -> None:
        super().__init__(
            message,
            code="vpn_error",
            details={"key_id": str(key_id)},
            **kwargs,
        )
        self.key_id = key_id


class PaymentException(AppException):
    """
    Raised when a payment or wallet operation fails.

    Args:
        order_id:  Affected order ID.
        method:    Payment method used (e.g. "wallet", "usdt").
    """
    default_code = "payment_error"
    default_http_status = 402

    def __init__(
        self,
        message: str,
        order_id: Any = None,
        method: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            code="payment_error",
            details={"order_id": str(order_id), "method": method},
            **kwargs,
        )
        self.order_id = order_id
        self.method = method
