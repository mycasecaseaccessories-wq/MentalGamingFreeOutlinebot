"""Navigation models used by the customer UI."""

from __future__ import annotations

from enum import StrEnum


class CustomerPage(StrEnum):
    HOME = "home"
    PACKAGES = "packages"
    FREE_TRIAL = "free_trial"
    MY_KEYS = "my_keys"
    WALLET = "wallet"
    PROFILE = "profile"
    SUPPORT = "support"