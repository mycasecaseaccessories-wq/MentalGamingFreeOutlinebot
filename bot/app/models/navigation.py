"""Transport-neutral navigation models for Phase 1.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CustomerMenuItem(StrEnum):
    """Stable identifiers for customer navigation destinations."""

    MAIN = "main"
    BUY_VPN = "buy_vpn"
    FREE_TRIAL = "free_trial"
    MY_KEYS = "my_keys"
    WALLET = "wallet"
    ORDERS = "orders"
    PAYMENTS = "payments"
    PROFILE = "profile"
    SUPPORT = "support"
    REFER_FRIENDS = "refer_friends"
    MISSIONS = "missions"


@dataclass(frozen=True, slots=True)
class NavigationDestination:
    """Presentation metadata returned by CustomerNavigationService."""

    item: CustomerMenuItem
    title_key: str
    body_key: str
    implemented: bool = False
