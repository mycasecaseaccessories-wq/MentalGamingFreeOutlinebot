"""
Domain models package.

Models represent the core business entities.
They are plain Python dataclasses / Pydantic models — not ORM models.
ORM-specific code lives in app/repositories/.
"""

from .enums import (
    Language,
    NotificationType,
    OrderStatus,
    PackageStatus,
    PackageType,
    PaymentMethod,
    Permission,
    ROLE_PERMISSIONS,
    ServerStatus,
    UserRole,
    UserStatus,
    VPNKeyStatus,
)
from .user import User

__all__ = [
    "UserRole",
    "UserStatus",
    "Language",
    "Permission",
    "ROLE_PERMISSIONS",
    "PackageType",
    "PackageStatus",
    "VPNKeyStatus",
    "ServerStatus",
    "OrderStatus",
    "PaymentMethod",
    "NotificationType",
    "User",
]
