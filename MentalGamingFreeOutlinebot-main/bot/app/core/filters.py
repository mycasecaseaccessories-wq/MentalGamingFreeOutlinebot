"""Transport-safe filter DTOs for repository and API boundaries."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import (
    OrderStatus,
    ServerStatus,
    UserRole,
    UserStatus,
    VPNKeyStatus,
)


class FilterBase(BaseModel):
    search: Optional[str] = Field(default=None, max_length=256)
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None


class UserFilter(FilterBase):
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    language: Optional[str] = None


class OrderFilter(FilterBase):
    status: Optional[OrderStatus] = None
    user_id: Optional[int] = Field(default=None, ge=1)
    package_id: Optional[int] = Field(default=None, ge=1)


class ServerFilter(FilterBase):
    status: Optional[ServerStatus] = None
    country_code: Optional[str] = Field(default=None, min_length=2, max_length=2)


class WalletFilter(FilterBase):
    user_id: Optional[int] = Field(default=None, ge=1)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=5)
    is_frozen: Optional[bool] = None


class VPNFilter(FilterBase):
    status: Optional[VPNKeyStatus] = None
    user_id: Optional[int] = Field(default=None, ge=1)
    server_id: Optional[int] = Field(default=None, ge=1)