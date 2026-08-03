"""
Shared enumerations for the platform.

Adding a new role:
  1. Add the value here.
  2. Update the permission matrix when it is implemented in Phase 0.2+.
"""

from enum import Enum, unique


@unique
class UserRole(str, Enum):
    """
    User roles within the platform.

    Current roles:
        ADMIN    — Full access; can manage servers, packages, and users.
        CUSTOMER — Regular subscriber; can buy and use VPN keys.

    Planned roles (Phase 2+):
        RESELLER  — Buys keys in bulk and resells them.
        AFFILIATE — Earns commissions via referral links.
    """

    ADMIN = "admin"
    CUSTOMER = "customer"
    # RESELLER = "reseller"   # Phase 2
    # AFFILIATE = "affiliate" # Phase 2


@unique
class Language(str, Enum):
    """
    Supported UI languages.

    Adding a new language:
      1. Add the value here.
      2. Create the corresponding file in locales/.
      3. Register it in locales/translator.py.
    """

    ENGLISH = "en"
    MYANMAR = "my"
