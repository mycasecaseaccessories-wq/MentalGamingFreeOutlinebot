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
