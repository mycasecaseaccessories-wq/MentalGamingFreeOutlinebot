"""
Database repositories package.

All data access logic lives here.  Each repository wraps SQL operations
for a single aggregate root (entity family) and returns domain objects.

Rules
-----
• Repositories MUST NOT contain business logic.
• Repositories MUST return domain model objects (or plain dicts), not raw ORM rows.
• Services MUST NOT write SQL directly — they call repository methods.
• All repository methods are async.

Available repositories
----------------------
UserRepository         — users table CRUD and lookup helpers.
PreferenceRepository   — per-user configurable preferences.
PackageRepository      — package catalogue management.
ServerRepository       — Outline server fleet management.
VPNKeyRepository       — key issuance, revocation, and expiry queries.
WalletRepository       — wallet balance and frozen-state management.
OrderRepository        — order lifecycle and history queries.
GrowthRepository       — referral relationships and commission tracking.
SettingsRepository     — typed key-value platform configuration.
NotificationRepository — notification dispatch queue and delivery status.
"""

from .base import BaseRepository
from .user_repository import UserRepository
from .preference_repository import PreferenceRepository
from .package_repository import PackageRepository
from .server_repository import ServerRepository
from .vpn_key_repository import VPNKeyRepository
from .wallet_repository import WalletRepository
from .order_repository import OrderRepository
from .growth_repository import GrowthRepository
from .settings_repository import SettingsRepository
from .notification_repository import NotificationRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "PreferenceRepository",
    "PackageRepository",
    "ServerRepository",
    "VPNKeyRepository",
    "WalletRepository",
    "OrderRepository",
    "GrowthRepository",
    "SettingsRepository",
    "NotificationRepository",
]
