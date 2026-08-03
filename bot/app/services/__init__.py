"""
Services package.

The service layer contains all business logic.
Services are the single source of truth for rules, validations, and workflows.

Services MUST NOT import from handlers or keyboards.
Services MAY import from repositories and other services.

Available services:
    SettingsService      — Runtime configuration, feature flags, and settings cache.
    UserService          — User account management and profile operations.
    PackageService       — VPN subscription package catalogue.
    WalletService        — In-platform wallet and balance management.
    ServerService        — Outline VPN server lifecycle management.
    VPNService           — VPN key provisioning and access control.
    GrowthService        — Referral programme and affiliate logic.
    NotificationService  — Multi-channel notification dispatch.
"""

from .settings_service import SettingsService
from .user_service import UserService
from .package_service import PackageService
from .wallet_service import WalletService
from .server_service import ServerService
from .vpn_service import VPNService
from .growth_service import GrowthService
from .notification_service import NotificationService

__all__ = [
    "SettingsService",
    "UserService",
    "PackageService",
    "WalletService",
    "ServerService",
    "VPNService",
    "GrowthService",
    "NotificationService",
]
