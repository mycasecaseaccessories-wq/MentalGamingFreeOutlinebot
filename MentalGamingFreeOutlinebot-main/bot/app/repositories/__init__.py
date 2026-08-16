"""
App-level repositories package.

In Phase 0.2 the canonical repository implementations moved to
database/repositories/ to keep all database code in one place.

This module re-exports them for backward compatibility so existing
service code importing from app.repositories continues to work without
changes.

Prefer importing directly from database.repositories in new code:
    from database.repositories import UserRepository
"""

# Re-export everything from the canonical location.
from database.repositories import (  # noqa: F401
    BaseRepository,
    UserRepository,
    PackageRepository,
    ServerRepository,
    VPNKeyRepository,
    WalletRepository,
    OrderRepository,
    GrowthRepository,
    SettingsRepository,
    NotificationRepository,
)

__all__ = [
    "BaseRepository",
    "UserRepository",
    "PackageRepository",
    "ServerRepository",
    "VPNKeyRepository",
    "WalletRepository",
    "OrderRepository",
    "GrowthRepository",
    "SettingsRepository",
    "NotificationRepository",
]
