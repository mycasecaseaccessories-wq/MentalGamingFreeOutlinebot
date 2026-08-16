"""Transport-neutral models for the Phase 1.1 customer entry flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.models.enums import UserRole, UserStatus


class EntryRoute(StrEnum):
    LANGUAGE_SELECTION = "language_selection"
    ADMIN = "admin"
    CUSTOMER = "customer"
    RESELLER = "reseller"
    AFFILIATE = "affiliate"
    MODERATOR = "moderator"
    VIP = "vip"
    ACCESS_RESTRICTED = "access_restricted"


@dataclass(frozen=True, slots=True)
class EntryDecision:
    """Decision returned by CustomerEntryService to the Telegram handler."""

    route: EntryRoute
    telegram_id: int
    role: UserRole
    status: UserStatus
    language: str
    is_new_user: bool = False
    start_parameter: str | None = None
    restriction_key: str | None = None
