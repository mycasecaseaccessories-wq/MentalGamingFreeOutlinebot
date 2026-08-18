"""
Services package.

The service layer contains all business logic.
Services are the single source of truth for rules, validations, and workflows.

Services MUST NOT import from handlers or keyboards.
Services MAY import from repositories and other services.

Available services:
    SettingsService      — Runtime configuration, feature flags, and settings cache.
    LanguageService      — Multilingual translation and per-user language preferences.
    UserService          — User account management and profile operations.
    PreferenceService    — Per-user configurable preferences (language, theme, tz, …).
    PackageService       — VPN subscription package catalogue.
    WalletService        — In-platform wallet and balance management.
    ServerService        — Outline VPN server lifecycle management.
    VPNService           — VPN key provisioning and access control.
    GrowthService        — Referral programme and affiliate logic.
    NotificationService  — Multi-channel notification dispatch.
"""

from .settings_service import SettingsService
from .language_service import LanguageService
from .user_service import UserService
from .preference_service import PreferenceService
from .package_service import PackageService
from .wallet_service import WalletService
from .wallet_payment_service import WalletPaymentService
from .manual_payment_service import ManualPaymentService
from .payment_submission_service import PaymentSubmissionService
from .payment_review_service import PaymentReviewService
from .history_service import HistoryService
from .server_service import ServerService
from .outline_setup_service import OutlineSetupService
from .ssh_discovery_service import SSHDiscoveryService
from .outline_provisioning_service import OutlineProvisioningService
from .vpn_service import VPNService
from .growth_service import GrowthService
from .growth_reward_service import GrowthRewardService
from .growth_reconciliation_service import GrowthReconciliationService
from .background_job_service import BackgroundJobService
from .notification_service import NotificationService
from .customer_entry_service import CustomerEntryService
from .order_service import OrderService
from .checkout_service import CheckoutService

__all__ = [
    "SettingsService",
    "LanguageService",
    "UserService",
    "PreferenceService",
    "PackageService",
    "WalletService",
    "WalletPaymentService",
    "ManualPaymentService",
    "PaymentSubmissionService",
    "PaymentReviewService",
    "HistoryService",
    "ServerService",
    "OutlineSetupService",
    "SSHDiscoveryService",
    "OutlineProvisioningService",
    "VPNService",
    "GrowthService",
    "GrowthRewardService",
    "GrowthReconciliationService",
    "BackgroundJobService",
    "NotificationService",
    "CustomerEntryService",
    "OrderService",
    "CheckoutService",
    "CustomerKeyService",
]

from .customer_navigation_service import CustomerNavigationService

from .profile_service import ProfileService

from .support_service import SupportService

from .package_catalog_service import PackageCatalogService

from .customer_key_service import CustomerKeyService
from .server_reservation_service import ServerReservationService
