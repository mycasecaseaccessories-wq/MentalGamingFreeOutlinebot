"""Transport DTOs shared by bot services and future API clients.

DTOs intentionally contain no business logic.  They provide stable,
serialisable contracts while domain and ORM models remain independent.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    NotificationType,
    OrderStatus,
    PackageStatus,
    PackageType,
    PaymentMethod,
    ServerStatus,
    UserRole,
    UserStatus,
    VPNKeyStatus,
)


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class UserDTO(DTO):
    telegram_id: int
    full_name: str
    username: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER
    status: UserStatus = UserStatus.ACTIVE
    language: str = "en"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PackageDTO(DTO):
    id: Optional[int] = None
    name: str
    package_type: PackageType = PackageType.PAID
    status: PackageStatus = PackageStatus.DRAFT
    price: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = "MMK"
    data_limit_gb: float = Field(default=0.0, ge=0)
    duration_days: int = Field(default=1, ge=1)


class WalletDTO(DTO):
    user_id: int
    balance: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = "MMK"
    is_frozen: bool = False


class VPNKeyDTO(DTO):
    id: Optional[int] = None
    user_id: int
    server_id: Optional[int] = None
    key_id: str
    access_url: Optional[str] = None
    status: VPNKeyStatus = VPNKeyStatus.PENDING
    expires_at: Optional[datetime] = None


class OrderDTO(DTO):
    """Customer-safe order contract; internal DB IDs are omitted from Telegram output."""
    id: Optional[int] = None
    user_id: int
    package_id: Optional[int] = None
    public_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    payment_status: str = "unpaid"
    payment_method: Optional[PaymentMethod] = None
    package_name: Optional[str] = None
    data_limit_gb: Optional[Decimal] = None
    duration_days: Optional[int] = None
    device_limit: Optional[int] = None
    total_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = "MMK"
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ServerDTO(DTO):
    id: Optional[int] = None
    name: str
    host: str
    status: ServerStatus = ServerStatus.PROVISIONING
    country_code: Optional[str] = None


class NotificationDTO(DTO):
    user_id: int
    notification_type: NotificationType = NotificationType.SYSTEM
    title: Optional[str] = None
    message: str
    sent_at: Optional[datetime] = None
    delivered: bool = False


class SettingsDTO(DTO):
    environment: str = "development"
    default_language: str = "en"
    default_currency: str = "MMK"
    timezone: str = "UTC"
    feature_flags: dict[str, bool] = Field(default_factory=dict)


class PaginationDTO(DTO):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    total: int = Field(default=0, ge=0)
    total_pages: int = Field(default=0, ge=0)
    has_next: bool = False
    has_previous: bool = False