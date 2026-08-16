"""
Shared enumerations for the platform.

Phase 0.4: Added UserStatus, Permission, and future role placeholders.

Adding a new role:
  1. Add the value here.
  2. Add the permission set to ROLE_PERMISSIONS below.
  3. Update seed_roles() in UserService.

Adding a new permission:
  1. Add the value to Permission.
  2. Assign it to the relevant roles in ROLE_PERMISSIONS.
"""

from enum import Enum, unique


@unique
class UserRole(str, Enum):
    """
    User roles within the platform.

    Current roles:
        ADMIN    — Full access; can manage servers, packages, and users.
        CUSTOMER — Regular subscriber; can buy and use VPN keys.

    Future roles (Phase 2+):
        RESELLER  — Buys keys in bulk and resells them.
        AFFILIATE — Earns commissions via referral links.
        MODERATOR — Manages users without full admin rights.
        VIP       — Premium subscriber with higher data limits / priority.
    """

    ADMIN = "admin"
    CUSTOMER = "customer"
    RESELLER = "reseller"       # Phase 2
    AFFILIATE = "affiliate"     # Phase 2
    MODERATOR = "moderator"     # Phase 2
    VIP = "vip"                 # Phase 2


@unique
class UserStatus(str, Enum):
    """
    Lifecycle status of a user account.

    ACTIVE    — Normal account; full access to platform features.
    INACTIVE  — Account exists but has not been used recently.
    SUSPENDED — Temporarily restricted (e.g. payment issue).
    BANNED    — Permanently blocked; no access to any feature.
    PENDING   — Registered but not yet verified or onboarded.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"
    PENDING = "pending"
    DELETED = "deleted"


@unique
class Permission(str, Enum):
    """
    Fine-grained platform permissions.

    Assigned to roles in ROLE_PERMISSIONS.
    Checked by role_required() and admin_required() decorators.

    Phase 0.4: constants defined; enforcement implemented in Phase 2.
    """

    MANAGE_USERS = "manage_users"
    """Create, edit, ban, and unban user accounts."""

    MANAGE_PACKAGES = "manage_packages"
    """Create, edit, and deactivate subscription packages."""

    MANAGE_SERVERS = "manage_servers"
    """Add, edit, and decommission Outline VPN servers."""

    MANAGE_WALLET = "manage_wallet"
    """Top up, freeze, and adjust user wallet balances."""

    MANAGE_ORDERS = "manage_orders"
    """View and manually resolve orders."""

    MANAGE_SETTINGS = "manage_settings"
    """Read and write platform settings and feature flags."""

    VIEW_ANALYTICS = "view_analytics"
    """Access platform-wide usage statistics."""

    BROADCAST = "broadcast"
    """Send broadcast messages to all or segmented users."""


@unique
class Language(str, Enum):
    """
    Supported UI languages.

    Adding a new language:
      1. Add the value here.
      2. Create locales/<code>/__init__.py with the TRANSLATIONS dict.
      3. Register it in the LanguageService SUPPORTED_LANGUAGES list.
    """

    ENGLISH = "en"
    MYANMAR = "my"


@unique
class PackageType(str, Enum):
    """
    VPN package types.

    PAID       — Standard paid subscription.
    FREE_TRIAL — Limited trial given to new users.
    PROMOTION  — Discounted or time-limited promotional package.
    REWARD     — Package awarded via referral, competition, etc.
    VIP        — Premium package with elevated quotas / priority.
    """
    PAID       = "paid"
    FREE_TRIAL = "free_trial"
    PROMOTION  = "promotion"
    REWARD     = "reward"
    VIP        = "vip"


@unique
class PackageStatus(str, Enum):
    """
    Lifecycle status of a VPN package offering.

    DRAFT    — Being configured; not visible to customers.
    ACTIVE   — Published and available for purchase.
    HIDDEN   — Exists but not shown in catalogues (e.g. legacy or invite-only).
    DISABLED — Temporarily unavailable.
    ARCHIVED — Retired; kept for historical orders only.
    """
    DRAFT    = "draft"
    ACTIVE   = "active"
    HIDDEN   = "hidden"
    DISABLED = "disabled"
    ARCHIVED = "archived"


@unique
class VPNKeyStatus(str, Enum):
    """
    Lifecycle status of a VPN access key.

    PENDING   — Created but not yet activated on the Outline server.
    ACTIVE    — Operational; user can connect.
    EXPIRED   — Subscription period ended.
    SUSPENDED — Temporarily deactivated (e.g. payment overdue).
    REVOKED   — Permanently cancelled; cannot be reinstated.
    RENEWING  — Automated renewal in progress.
    """
    PENDING   = "pending"
    ACTIVE    = "active"
    EXPIRED   = "expired"
    SUSPENDED = "suspended"
    REVOKED   = "revoked"
    RENEWING  = "renewing"


@unique
class ServerStatus(str, Enum):
    """
    Operational status of an Outline VPN server.

    ONLINE        — Healthy and accepting connections.
    OFFLINE       — Unreachable or shut down.
    MAINTENANCE   — Intentionally taken offline for maintenance.
    DISABLED      — Excluded from key allocation.
    PROVISIONING  — Being set up; not yet ready for use.
    """
    UNKNOWN      = "unknown"
    ONLINE       = "online"
    OFFLINE      = "offline"
    MAINTENANCE  = "maintenance"
    DISABLED     = "disabled"
    PROVISIONING = "provisioning"
    ARCHIVED     = "archived"


@unique
class OrderStatus(str, Enum):
    """
    Lifecycle status of a purchase order.

    PENDING         — Created; awaiting payment selection.
    WAITING_PAYMENT — Payment instructions sent; awaiting confirmation.
    PAID            — Payment confirmed; VPN key being provisioned.
    CANCELLED       — Order cancelled by user or admin.
    EXPIRED         — Payment window elapsed without payment.
    REFUNDED        — Payment returned to user's wallet.
    COMPLETED       — VPN key successfully issued.
    """
    PENDING         = "pending"
    WAITING_PAYMENT = "waiting_payment"
    PAID            = "paid"
    CANCELLED       = "cancelled"
    EXPIRED         = "expired"
    REFUNDED        = "refunded"
    COMPLETED      = "completed"
    # Legacy value retained for rows created before Phase 2.1.
    FULFILLED      = "fulfilled"



@unique
class PaymentMethod(str, Enum):
    """
    Supported payment methods.

    WALLET — Deducted from the user's platform wallet balance.
    MANUAL — Manual transfer verified by an admin.
    USDT   — USDT (Tether) stablecoin transfer.
    BANK   — Bank transfer / mobile banking.
    """
    WALLET = "wallet"
    MANUAL = "manual"
    USDT   = "usdt"
    BANK   = "bank"
    # Future: KPAY = "kpay", WAVEPAY = "wavepay", STRIPE = "stripe"


@unique
class NotificationType(str, Enum):
    """
    Categories of user notifications.

    SYSTEM    — Platform-wide announcements or alerts.
    WALLET    — Top-up confirmations, low-balance warnings.
    ORDER     — Order status updates (paid, completed, cancelled).
    PROMOTION — Marketing messages and special offers.
    BROADCAST — Admin-sent mass messages.
    SECURITY  — Suspicious activity or account-action alerts.
    """
    SYSTEM    = "system"
    WALLET    = "wallet"
    ORDER     = "order"
    PROMOTION = "promotion"
    BROADCAST = "broadcast"
    SECURITY  = "security"


# ---------------------------------------------------------------------------
# Role → permission mapping
# ---------------------------------------------------------------------------
# Maps each role to the set of permissions it holds by default.
# Phase 0.4: constants only.  Enforcement is Phase 2.

ROLE_PERMISSIONS: dict[str, list[str]] = {
    UserRole.ADMIN: [p.value for p in Permission],   # All permissions
    UserRole.CUSTOMER: [],                             # No admin permissions
    UserRole.RESELLER: [
        Permission.MANAGE_ORDERS.value,
    ],
    UserRole.AFFILIATE: [],
    UserRole.MODERATOR: [
        Permission.MANAGE_USERS.value,
        Permission.VIEW_ANALYTICS.value,
    ],
    UserRole.VIP: [],
}
