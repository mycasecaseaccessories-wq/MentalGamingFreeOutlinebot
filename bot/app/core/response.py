"""Unified response envelope for services and future HTTP/API adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from app.core.exceptions import AppException

T = TypeVar("T")


class ResponseError(BaseModel):
    """A serialisable, client-safe error entry."""

    code: str
    message: str
    field: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class StandardResponse(BaseModel, Generic[T]):
    """Common success/failure response shape across future transports."""

    success: bool
    message: str = ""
    data: Optional[T] = None
    errors: list[ResponseError] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    request_id: Optional[str] = None

    @classmethod
    def ok(
        cls,
        data: Optional[T] = None,
        *,
        message: str = "OK",
        request_id: Optional[str] = None,
    ) -> "StandardResponse[T]":
        return cls(
            success=True,
            message=message,
            data=data,
            request_id=request_id,
        )

    @classmethod
    def fail(
        cls,
        message: str,
        *,
        code: str = "app_error",
        field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> "StandardResponse[T]":
        return cls(
            success=False,
            message=message,
            errors=[
                ResponseError(
                    code=code,
                    message=message,
                    field=field,
                    details=details or {},
                )
            ],
            request_id=request_id,
        )

    @classmethod
    def from_exception(
        cls,
        exc: AppException,
        *,
        request_id: Optional[str] = None,
    ) -> "StandardResponse[T]":
        return cls.fail(
            exc.message,
            code=exc.code,
            field=getattr(exc, "field", None),
            details=exc.details,
            request_id=request_id,
        )