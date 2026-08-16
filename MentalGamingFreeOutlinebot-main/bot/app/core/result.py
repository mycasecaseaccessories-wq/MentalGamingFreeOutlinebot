"""Small, typed Result pattern for service boundaries.

Results make expected failures explicit without forcing transport concerns
into services.  Existing services may continue to raise AppException; this
module is an opt-in contract for new code.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class ResultError:
    code: str
    message: str
    field: Optional[str] = None
    details: dict[str, object] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class Result(Generic[T]):
    value: Optional[T] = None
    error: Optional[ResultError] = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return self.error is not None

    def unwrap(self) -> T:
        """Return the value or raise a descriptive ValueError."""
        if self.error is not None:
            raise ValueError(f"{self.error.code}: {self.error.message}")
        return self.value  # type: ignore[return-value]

    def map(self, transform: Callable[[T], U]) -> "Result[U]":
        """Transform a successful value while preserving failures."""
        if self.error is not None:
            return Result(error=self.error)
        return Success(transform(self.value))  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        if self.error is not None:
            return {"success": False, "error": self.error}
        return {"success": True, "data": self.value}


Success = Result


def Failure(
    code: str,
    message: str,
    *,
    field: Optional[str] = None,
    details: Optional[dict[str, object]] = None,
) -> Result[object]:
    return Result(
        error=ResultError(
            code=code,
            message=message,
            field=field,
            details=details or {},
        )
    )


def ValidationError(
    message: str,
    *,
    field: Optional[str] = None,
    details: Optional[dict[str, object]] = None,
) -> Result[object]:
    return Failure("validation_error", message, field=field, details=details)


def PermissionError(message: str = "Permission denied.") -> Result[object]:
    return Failure("permission_denied", message)


def NotFound(message: str = "Resource not found.") -> Result[object]:
    return Failure("not_found", message)